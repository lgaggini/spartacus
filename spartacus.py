#! /usr/bin/env python
# documentazione api proxmox:
# https://pve.proxmox.com/pve-docs/api-viewer/index.html
# documentazione pyproxmox:
# https://github.com/Daemonthread/pyproxmox

from pyproxmox import *
import time

import sys
import random
import logging
import coloredlogs
import argparse
import socket
from settings.settings import PROXMOX, VM_RESOURCES, VM_DEFAULTS, KVM_THRES
from settings.settings import IMAGES_BASEPATH, WORKING_MNT
import rawinit
import yaml
import re
from yamlschema import vm_schema, VMDefValidator


logger = logging.getLogger('spartacus')


def log_init():
    FORMAT = '%(asctime)s %(levelname)s %(module)s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    coloredlogs.install(level='INFO')


def randomMAC():
    """ generate a random mac address """
    return [0x00,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff)]


def MACprettyprint(mac):
    return ':'.join(map(lambda x: "%02x" % x, mac))


def getNFSVolume(connessione, name):
    """ choose the storage volume based on vm index and check
    for available space """

    volume = VM_DEFAULTS['ODD_VOL']

    m = re.search(r'\d+$', name)
    if m is not None:
        index = m.group()
        logger.debug(index)
        if int(index) % 2 == 0:
            volume = VM_DEFAULTS['EVEN_VOL']

    storage = check_proxmox_response(connessione.getNodeStorage(
                                     PROXMOX['HOST'].split('.')[0]))
    logger.debug(storage)

    for s in storage['data']:
        if volume in s['storage']:
            avail = s['avail']
            logger.debug(avail)
            if avail <= KVM_THRES['SPACE']:
                logger.error('available space %s is under the minimum allowed (%s) on \
                              %s' % (avail, KVM_THRES['SPACE'], volume))
                sys.exit('exiting')

    return volume


def findTemplate(connessione, vmname):
    """ look for the provided template and return id and
    location """
    nodes = check_proxmox_response(connessione.getClusterNodeList())
    for node in nodes['data']:
        n = node['node']
        machines = check_proxmox_response(connessione.getNodeVirtualIndex(n))
        for m in machines['data']:
            logger.debug(m['name'])
            if (m['name'] == vmname):
                return m['vmid'], n
    return None, None


def getAvailableNode(connessione, memory):
    """choose the host wit more resources available"""
    d = {}
    nodes = check_proxmox_response(connessione.getClusterNodeList())
    for node in nodes['data']:
        n = node['node']
        status = check_proxmox_response(connessione.getNodeStatus(n))
        ncpu = status['data']['cpuinfo']['cpus']
        cpu1 = int(float(status['data']['loadavg'][0]))
        cpu5 = int(float(status['data']['loadavg'][1]))
        totram = status['data']['memory']['total']/1048576
        freeram = status['data']['memory']['free']/1048576
        percram = int(freeram * 100 / totram)
        magic = ncpu - (cpu1 + cpu5)/2 + int(percram)
        logger.debug('%s %s %s %s %s %s %s' % (n, cpu1, cpu5, totram,
                                               freeram, percram, magic))
        d[n] = {'magic': magic, 'freeram': freeram}

    for node_stat in sorted(d.items(), key=lambda x: x[1]['magic'],
                            reverse=True):
        logger.debug(node_stat)
        logger.debug(node_stat[1])
        if node_stat[1]['magic'] >= KVM_THRES['MAGIC'] and\
           node_stat[1]['freeram'] > int(memory) + KVM_THRES['MEMORY']:
            return node_stat[0]
    logger.error("no host with available resources found")
    sys.exit('exiting')


def check_proxmox_response(response):
    status_code = response['status']['code']
    if status_code != 200:
        reason = response['status']['reason']
        logger.error('proxmox api error, response code %s: %s' %
                     (status_code, reason))
        sys.exit('exiting')
    else:
        return response


def valid_ip_address(ip_address):
    """ custom parser validator for ip address """
    try:
        socket.inet_aton(ip_address)
        return ip_address
    except socket.error:
        raise argparse.ArgumentTypeError('%s is an invalid ip address'
                                         % ip_address)


def valid_netmask(netmask):
    """ custom argparse validator for netmask """
    valid_ip_address(netmask)
    seen0 = False
    for x in netmask.split('.'):
        logger.debug(bin(int(x))[2:])
        for c in bin(int(x))[2:]:
            if '1' == c:
                if seen0:
                    raise argparse.ArgumentTypeError('%s is an invalid netmask'
                                                     % netmask)
            else:
                seen0 = True
    return netmask


def valid_yaml_inventory(yaml_inventory):
    """ custom argparse validator for input file """
    if not os.path.exists(yaml_inventory):
        raise arparse.ArgumentTypeError('the file %s does not exist!'
                                        % yaml_inventory)
    else:
        return yaml_inventory


def valid_yaml_schema(yaml, schema):
    """ validator for the yaml inventory """
    validator = VMDefValidator(schema)
    logger.debug(yaml)
    normalized_yaml = validator.normalized(yaml)
    isvalid = validator.validate(normalized_yaml)
    return normalized_yaml, isvalid, validator.errors


def valid_vmid(vmid):
    """ validator for the proxmox vmid """
    if not vmid == 'auto' and int(vmid) > 999:
        raise argparse.ArgumentTypeError('invalid vmid: %s' % vmid)
    else:
        return vmid


def yaml_parse(path, schema):
    """ yaml parser of the inventory file """
    with open(path, 'r') as yaml_stream:
        try:
            options = yaml.safe_load(yaml_stream)
        except yaml.YAMLError, ex:
            logger.error('YAML parsing exception: ' + str(ex))
            sys.exit('exiting')
        options, isvalid, errors = valid_yaml_schema(options, schema)
        if isvalid:
            return options
        else:
            logger.error('YAML schema error: ')
            logger.error(errors)
            sys.exit('exiting')


if __name__ == '__main__':

    log_init()

    description = "spartacus, deploy vm on proxmox cluster"
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('-t', '--template', default=VM_DEFAULTS['TEMPLATE'],
                        help='Name of template to clone \
                        (default %s)' % VM_DEFAULTS['TEMPLATE'])
    parser.add_argument('--templateid', default=VM_DEFAULTS['TEMPLATEID'],
                        help='id of the template to clone \
                        (default %s)' % VM_DEFAULTS['TEMPLATEID'])
    parser.add_argument('--vmid', default='auto', type=valid_vmid,
                        help='the vmid for the new vm')
    parser.add_argument('-n', '--name', default=None,
                        help='Name of new virtual machines')
    parser.add_argument('-i', '--inventory', default=None,
                        help='Yaml file path to read')
    parser.add_argument('-d', '--description', help='description for new vm')
    parser.add_argument('--vlan', '--net', choices=VM_RESOURCES['VLANS'],
                        help='vlan for the first interface')
    parser.add_argument('--auto', action='store_true',
                        help='allow auto for the first interface')
    parser.add_argument('--hot', action='store_true',
                        help='allow hotplug for the first interface')
    parser.add_argument('--ipaddress', type=valid_ip_address,
                        help='first interface ip address')
    parser.add_argument('--netmask', type=valid_netmask,
                        help='first interface netmask')
    parser.add_argument('--gateway', type=valid_ip_address,
                        help='first interface gateway')
    parser.add_argument('-m', '--memory', default='4096',
                        choices=VM_RESOURCES['RAM'],
                        help='MB of ram to be allocated (default 4096)')
    parser.add_argument('-c', '--cores', default='2',
                        choices=VM_RESOURCES['CORES'],
                        help='# of cores (default 2)')
    parser.add_argument('-s', '--sockets', default='2',
                        choices=VM_RESOURCES['SOCKETS'],
                        help='# of socket (default 2)')
    parser.add_argument('-f', '--farm', default='farm1',
                        choices=VM_RESOURCES['FARMS'],
                        help='farm for puppet')
    parser.add_argument('-e', '--env', help='environment for puppet')

    options = {}

    cli_options = parser.parse_args()
    logger.debug(cli_options)

    if cli_options.name is None and cli_options.inventory is None:
        parser.print_help()
        logger.error('argument -n/--name or -i/--inventory are required')
        sys.exit('exiting')

    if cli_options.name is None and cli_options.inventory is not None:
        parsed_options = yaml_parse(cli_options.inventory, vm_schema)
        logger.debug(parsed_options)
        logger.debug(parsed_options['template'])
        options = parsed_options
    else:
        options = vars(cli_options)
        # fix networks
        options['interfaces'] = []
        network = {'vlan': cli_options.vlan, 'auto': cli_options.auto,
                   'hot': cli_options.hot, 'ipaddress': cli_options.ipaddress,
                   'netmask': cli_options.netmask,
                   'gateway': cli_options.gateway}
        options['networks'] = []
        options['networks'].append(network)
        # fix hosts

    logger.debug(options)

    logger.info('connecting to %s' % PROXMOX['HOST'])
    auth = prox_auth(PROXMOX['HOST'], PROXMOX['USER'], PROXMOX['PASSWORD'])
    proxmox_api = pyproxmox(auth)

    vm_name = options['template']
    name = options['name']
    description = options['description']
    logger.info('looking for the template %s' % vm_name)
    if options['templateid'] is None or\
       options['template'] != VM_DEFAULTS['TEMPLATE']:
        tid, node = findTemplate(proxmox_api, vm_name)
    else:
        tid = options['templateid']
        node = VM_DEFAULTS['TEMPLATENODE']
    logger.info('template %s, tid %s found'
                % (options['template'], tid))

    if (tid is not None):

        if 'auto' in options['vmid']:
            # prende il primo id disponibile
            newid = check_proxmox_response(proxmox_api.getClusterVmNextId())['data']
        else:
            newid = options['vmid']

        logger.info('VmNextId: %s found' % newid)

        target_node = getAvailableNode(proxmox_api, options['memory'])
        logger.info('available node: %s found' % target_node)
        storage = getNFSVolume(proxmox_api, options['name'])
        logger.info('storage: %s found' % storage)

        # installa una macchina clonando il template
        install = [('newid', newid), ('name', name), ('full', 1),
                   ('format', 'raw'), ('storage', storage),
                   ('target', target_node), ('description', description)]
        logger.info('installing the vm %s (id %s)' % (name, newid))
        logger.info('cloning template %s (id %s) on node %s' %
                    (vm_name, tid, target_node))
        logger.info('using storage %s' % storage)
        check_proxmox_response(proxmox_api.cloneVirtualMachine(node, tid, install))
        logger.info('starting the clone')

        while True:
            vstatus = proxmox_api.getVirtualStatus(target_node, newid)
            if vstatus['status']['ok'] is True:
                break
            logger.info('waiting 5 seconds')
            time.sleep(5)

        mod_conf = []
        for i, interface in enumerate(options['interfaces']):
            if (interface['vlan'] is not None):
                str = 'virtio=' + MACprettyprint(randomMAC()) +\
                      ',bridge=vmbr' + interface['vlan']
                mod_conf.append(('net%s' % i, str))
                logger.debug(mod_conf)
                interface['id'] = '%s%i' % (VM_DEFAULTS['STARTNIC'],
                                            VM_DEFAULTS['STARTNICID']+i)
                logger.debug(interface['id'])
        mod_conf.append(('memory', options['memory']))
        mod_conf.append(('cores', options['cores']))
        mod_conf.append(('sockets', options['sockets']))
        logger.debug(mod_conf)
        time.sleep(10)
        logger.info('clone end')
        check_proxmox_response(proxmox_api.setVirtualMachineOptions
                               (target_node, newid, mod_conf))
        logger.info('options settings')

        newimage = 'vm-%s-disk-1.raw' % newid
        src = '%s/%s/images/%s/%s' % (IMAGES_BASEPATH, storage, newid,
                                      newimage)
        logger.debug(src)
        dst = '%s/%s' % (WORKING_MNT, newid)
        logger.debug(dst)

        rawinit.rawinit(options, src, dst)

        logger.debug(proxmox_api.getVirtualConfig(target_node, newid))
        check_proxmox_response(proxmox_api.startVirtualMachine(
                               target_node, newid))
        logger.info('starting the vm %s (id %s) on node %s' %
                    (name, newid, target_node))
    else:
        logger.error('unable to found template %s' % (vm_name))
        sys.exit(2)
