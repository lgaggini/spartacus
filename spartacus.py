#! /usr/bin/env python
# documentazione api proxmox:
# https://pve.proxmox.com/pve-docs/api-viewer/index.html
# documentazione pyproxmox:
# https://github.com/Daemonthread/pyproxmox

import pyproxmox
import time

import sys
import random
import logging
import coloredlogs
import argparse
import socket
from settings.settings import AVAILABLE_VLANS, AVAILABLE_FARMS
from settings.settings import RAM_SIZES, CORE_SIZES, SOCKET_SIZES
import yaml


logger = logging.getLogger(__file__)


def log_init():
    FORMAT = '%(asctime)s %(levelname)s %(module)s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    coloredlogs.install(level='INFO')


def randomMAC():
    return [0x00,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff)]


def MACprettyprint(mac):
    return ':'.join(map(lambda x: "%02x" % x, mac))


def getNFSVolume(connessione, name):
    """prende il volume attivo pveXX in base all indice della
    macchina e controlla lo spazio disponibile"""

    volume = 'pve03'

    m = re.search(r'\d+$', name)
    if m is not None:
        index = m.group()
        if index % 2 == 0:
            volume = 'pve04'

    storage = connessione.getNodeStorage('kvm')
    logger.debug(storage)

    for s in storage['data']:
        logger.debug(s['content'])
        if volume in s['storage']:
            avail = s['avail']
            logger.debug(avail)
            if avail <= 100000000:
                logger.error('Available space %s is under the minimum allowed (%s) on \
                              %s' % (avail, 100000000, volume))
                sys.exit('exiting')

    return volume


def findTemplate(connessione, vmname):
    """ dato il nome del template (vmname) ritorna """
    """ su quale nodo kvm si trova e qual e' l'id """
    """ se non trova niente ritorna None, None """
    nodes = connessione.getClusterNodeList()
    for node in nodes['data']:
        n = node['node']
        machines = connessione.getNodeVirtualIndex(n)
        for m in machines['data']:
            logging.debug(m['name'])
            if (m['name'] == vmname):
                return m['vmid'], n
    return None, None


def getAvailableNode(connessione):
    """calcola qual e' la macchina piu' scarica"""
    d = {}
    nodes = connessione.getClusterNodeList()
    for node in nodes['data']:
        n = node['node']
        status = connessione.getNodeStatus(n)
        ncpu = status['data']['cpuinfo']['cpus']
        cpu1 = int(float(status['data']['loadavg'][0]))
        cpu5 = int(float(status['data']['loadavg'][1]))
        totram = status['data']['memory']['total']/1048576
        freeram = status['data']['memory']['free']/1048576
        percram = int(freeram * 100 / totram)
        magic = ncpu - (cpu1 + cpu5)/2 + int(percram)
        logger.debug('%s %s %s %s %s %s %s' % (n, cpu1, cpu5, totram,
                                               freeram, percram, magic))
        d[n] = magic

        for w in sorted(d, key=d.get, reverse=True):
            if d[w] >= 40:
                return w
    return None


def valid_ip_address(ip_address):
    try:
        socket.inet_aton(ip_address)
        return ip_address
    except socket.error:
        raise argparse.ArgumentTypeError("%s is an invalid ip address"
                                         % ip_address)


def valid_yaml_inventory(yaml_inventory):
    if not os.path.exists(yaml_inventory):
        parser.error("The file %s does not exist!" % arg)
    # TODO: schema validation
    # elif
    #
    else:
        return yaml_inventory


def yaml_parse(path):
    with open(path, 'r') as yaml_stream:
        try:
            options = yaml.safe_load(yaml_stream)
        except yaml.YAMLError, ex:
            logger.error('YAML parsing exception: ' + str(ex))
            sys.exit('exiting')
    return options


if __name__ == '__main__':

    log_init()

    description = "spartacus, deploy vm on proxmox cluster"
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('-t', '--template', default='masterdebian9',
                        help='Name of template to clone \
                        (default masterdebian9)')
    parser.add_argument('-n', '--name', default=None,
                        help='Name of new virtual machines')
    parser.add_argument('-i', '--inventory', default=None,
                        help='Yaml file path to read')
    parser.add_argument('-d', '--description', help='description for new vm')
    parser.add_argument('--vlan', '--net', choices=AVAILABLE_VLANS,
                        help='vlan for the first interface')
    parser.add_argument('--auto', action='store_true',
                        help='allow auto for the first interface')
    parser.add_argument('--hot', action='store_true',
                        help='allow hotplug for the first interface')
    parser.add_argument('--ipaddress', type=valid_ip_address,
                        help='first interface ip address')
    parser.add_argument('--netmask', type=valid_ip_address,
                        help='first interface netmask')
    parser.add_argument('--gateway', type=valid_ip_address,
                        help='first interface gateway')
    parser.add_argument('-m', '--memory', default='4096', choices=RAM_SIZES,
                        help='MB of ram to be allocated (default 4096)')
    parser.add_argument('-c', '--cores', default='2', choices=CORE_SIZES,
                        help='# of cores (default 2)')
    parser.add_argument('-s', '--sockets', default='2', choices=SOCKET_SIZES,
                        help='# of socket (default 2)')
    parser.add_argument('-f', '--farm', default='farm1',
                        choices=AVAILABLE_FARMS, help='farm for puppet')
    parser.add_argument('-e', '--env', help='environment for puppet')

    options = {}

    cli_options = parser.parse_args()
    logger.debug(cli_options)

    if cli_options.name is None and cli_options.inventory is None:
        parser.print_help()
        logger.error('argument -n/--name or -i/--inventory are reuired')
        sys.exit('exiting')

    if cli_options.name is None and cli_options.inventory is not None:
        parsed_options = yaml_parse(cli_options.inventory)
        logger.debug(parsed_options)
        logger.debug(parsed_options['template'])
        options = parsed_options
    else:
        options = vars(cli_options)
        # fix networks
        options['networks'] = []
        network = {'vlan': cli_options.vlan, 'auto': cli_options.auto,
                   'hot': cli_options.hot, 'ipaddress': cli_options.ipaddress,
                   'netmask': cli_options.netmask,
                   'gateway': cli_options.gateway}
        options['networks'].append(network)
        # fix hosts

    logger.debug(options)

    sys.exit(0)

    logger.info("mi connetto")
    auth = prox_auth('kvm.domain', 'root@pam', 'password')
    proxmox = pyproxmox(auth)


    vm_name = options['template']
    name = options['name']
    logger.info("cerco il template")
    vmid, node = findTemplate(proxmox, vm_name)

    if (vmid is not None):
        # prende il primo id disponibile
        newid = proxmox.getClusterVmNextId()['data']

        logger.info("ho trovato il VmNextId")
        logger.info("ho trovato il nodo disponibile")
        logger.info("ho trovato lo storage")
        target_node = getAvailableNode(proxmox)
        storage = getNFSVolume(proxmox, options['name'])

        # installa una macchina clonando il template
        install = [('newid', newid), ('name', name), ('full', 1),
                   ('format', 'raw'), ('storage', storage),
                   ('target', target_node)]
        logger.info("installo la macchina %s (id %s) clonando il template %s \
                    (id %s su macchina %s) sul nodo %s utilizzando lo storage \
                    %s" % (name, newid, vm_name, vmid, node, target_node,
                    storage))
        # proxmox.cloneVirtualMachine(node, vmid, install)
        logger.info("inizio la clonazione")

        # while True:
        #    if proxmox.getVirtualStatus(target_node, newid)['status']['ok']\
        #       is True:
        #        break
        #    logger.info("aspetto altri 5 secondi")
        #    time.sleep(5)

        logger.info("finita la clonazione")
        # config = b.getVirtualConfig(target_node,newid)['data']['net0']
        mod_conf = []
        if (options['vlan'] is not None):
            str = 'virtio=' + MACprettyprint(randomMAC()) +\
                  ',bridge=vmbr' + options['vlan']
            mod_conf.append(('net0', str))
        mod_conf.append(('memory', options['memory']))
        mod_conf.append(('cores', options['cores']))
        mod_conf.append(('sockets', options['sockets']))
        logger.debug(mod_conf)
        # proxmox.setVirtualMachineOptions(target_node, newid, mod_conf)
        logger.info("setto le opzioni")
        # TODO: montare il volume della macchina e modificare hostname,
        # hosts e conf di rete
        # logger.debug(proxmox.getVirtualConfig(target_node, newid))
        # proxmox.startVirtualMachine(target_node, newid)
        logger.info("accendo la macchina")
    else:
        logger.error("impossibile trovare il template %s" % (vm_name))
        sys.exit(2)
