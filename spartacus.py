#! /usr/bin/env python

from pyproxmox import *
import time

import sys
import random
import logging
import coloredlogs
import argparse
import socket
import rawinit
import yaml
import re
from yamlschema import vm_schema, VMDefValidator
import operator
import importlib
import os

SETTINGS_KEY = ['PROXMOX', 'SSH_HOST_KEY', 'DEV', 'TMP_DIR', 'STATIC_DIR',
                'VM_RESOURCES', 'VM_DEFAULTS', 'VM_DEFAULTS8', 'KVM_THRES',
                'IMAGES_BASEPATH', 'TEMPLATE_MAP', 'WORKING_MNT']
LOG_LEVELS = ['debug', 'info', 'warning', 'error', 'critical']

logger = logging.getLogger('spartacus')


def log_init(loglevel):
    """ initialize the logging system """
    FORMAT = '%(asctime)s %(levelname)s %(module)s %(message)s'
    logging.basicConfig(format=FORMAT, level=getattr(logging,
                                                     loglevel.upper()))
    coloredlogs.install(level=loglevel.upper())


def settings_load(settings_file):
    """ load settings from settings package """
    logger.info('loading settings from %s' % (settings_file))
    try:
        settings_basename = os.path.basename(settings_file)
        module_name = 'settings.%s' % (os.path.splitext(settings_basename)[0])
        logger.debug(module_name)
        settings_module = importlib.import_module(module_name)
    except ImportError, ex:
        logger.error('no such file: %s' % (settings_file))
        sys.exit('exiting')
    settings = {}
    try:
        for setting in SETTINGS_KEY:
            settings[setting] = getattr(settings_module, setting)
    except AttributeError, ex:
        logger.error('settings loading error: %s' % (ex))
        sys.exit('exiting')
    return settings


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
    """ choose the storage volume based on vm index, check
    for available space and selecte the bigger one """

    selected_volumes = {}

    volumes = cfg['VM_DEFAULTS']['ODD_VOL']

    m = re.search(r'\d+$', name)
    if m is not None:
        index = m.group()
        logger.debug(index)
        if int(index) % 2 == 0:
            volumes = cfg['VM_DEFAULTS']['EVEN_VOL']

    storage = check_proxmox_response(connessione.getNodeStorage(
                                     cfg['PROXMOX']['HOST'].split('.')[0]))
    logger.debug(storage)

    for s in storage['data']:
        for volume in volumes:
            logger.debug(volume)
            if volume in s['storage']:
                avail = s['avail']
                logger.debug(avail)
                if avail <= cfg['KVM_THRES']['SPACE']:
                    logger.debug('available space %s is under the minimum \
                                 allowed (%s) on %s' %
                                 (avail, cfg['KVM_THRES']['SPACE'], volume))
                    continue
                else:
                    selected_volumes[volume] = avail

    logger.debug(selected_volumes)
    if not any(selected_volumes):
        logger.error('no available space on selected volumes: %s' %
                     (','.join(volumes)))
        sys.exit('exiting')
    else:
        return sorted(selected_volumes.items(),
                      key=operator.itemgetter(1))[0][0]


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
        if node['status'] == 'online':
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
        if node_stat[1]['magic'] >= cfg['KVM_THRES']['MAGIC'] and\
           node_stat[1]['freeram'] > int(memory) + cfg['KVM_THRES']['MEMORY']:
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


def yaml_parse(path, schema):
    """ yaml parser of the inventory file """
    with open(path, 'r') as yaml_stream:
        try:
            options = yaml.safe_load(yaml_stream)
        except yaml.YAMLError, ex:
            logger.error('YAML parsing exception: %s' % str(ex))
            sys.exit('exiting')
        options, isvalid, errors = valid_yaml_schema(options, schema)
        if isvalid:
            return options
        else:
            logger.error('YAML schema error: ')
            logger.error(errors)
            sys.exit('exiting')


if __name__ == '__main__':

    description = "spartacus, deploy vm on proxmox cluster"
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('-s', '--settings', default='settings',
                        help='custom settings file in settings package')
    parser.add_argument('-i', '--inventory', default=None,
                        help='Yaml file path to read', required=True)
    parser.add_argument('-n', '--no-rawinit', dest='init',
                        action='store_false',
                        help='disable the rawinit component (default enabled)')
    parser.set_defaults(init=True)
    parser.add_argument('-r', '--readonly', dest='readonly',
                        action='store_true',
                        help='readonly mode for debug (default disabled)')
    parser.set_defaults(readonly=False)
    parser.add_argument('-l', '--log-level', default=LOG_LEVELS[1],
                        help='log level (default info)', choices=LOG_LEVELS)

    # parse cli options
    options = {}
    cli_options = parser.parse_args()
    log_init(cli_options.log_level)
    logger.debug(cli_options)

    # load settings from setting package
    global cfg
    cfg = settings_load(cli_options.settings)
    logger.debug(cfg)

    # load desired config from yaml
    parsed_options = yaml_parse(cli_options.inventory, vm_schema)
    logger.debug(parsed_options)
    logger.debug(parsed_options['template'])
    options = parsed_options
    # fix rawinit
    options['init'] = cli_options.init
    # fix puppet
    options['puppet'] = {}
    options['puppet']['puppetmaster'] = options['puppetmaster']
    options['puppet']['env'] = options['env']
    # fix readonly
    options['readonly'] = cli_options.readonly
    readonly = options['readonly']
    logger.debug(options)

    # authentication on proxmox
    logger.info('connecting to %s' % cfg['PROXMOX']['HOST'])
    auth = prox_auth(cfg['PROXMOX']['HOST'], cfg['PROXMOX']['USER'],
                     cfg['PROXMOX']['PASSWORD'])
    proxmox_api = pyproxmox(auth)

    # looking for template / src vm to clone
    vm_name = options['template']
    name = options['name']
    description = options['description']
    logger.info('looking for the template %s' % vm_name)
    if options['templateid'] is None or\
       options['template'] != cfg['VM_DEFAULTS']['TEMPLATE']:
        tid, node = findTemplate(proxmox_api, vm_name)
    else:
        tid = options['templateid']
        node = cfg['VM_DEFAULTS']['TEMPLATENODE']
    logger.info('template %s, tid %s found'
                % (options['template'], tid))

    # template found, maybe
    if (tid is not None):
        # looking for next availabe vmid
        if 'auto' in options['vmid']:
            newid = check_proxmox_response(proxmox_api.getClusterVmNextId()
                                           )['data']
        else:
            newid = options['vmid']
        logger.info('VmNextId: %s found' % newid)

        # get node best matching vm requirements
        target_node = getAvailableNode(proxmox_api, options['memory'])
        logger.info('available node: %s found' % target_node)
        storage = getNFSVolume(proxmox_api, options['name'])
        logger.info('storage: %s found' % storage)

        # clone
        install = [('newid', newid), ('name', name), ('full', 1),
                   ('format', 'raw'), ('storage', storage),
                   ('target', target_node), ('description', description)]
        logger.info('installing the vm %s (id %s)' % (name, newid))
        logger.info('cloning template %s (id %s) on node %s' %
                    (vm_name, tid, target_node))
        logger.info('using storage %s' % storage)
        if not readonly:
            check_proxmox_response(proxmox_api.cloneVirtualMachine(node, tid,
                                                                   install))
        logger.info('starting the clone')

        if not readonly:
            while True:
                vstatus = proxmox_api.getVirtualStatus(target_node, newid)
                if vstatus['status']['code'] == 200 \
                   and vstatus['data']['name'] == name:
                    break
                logger.info('waiting 5 seconds')
                time.sleep(5)

        logger.info('clone end')

        # customize new vm settings
        mod_conf = []
        for i, interface in enumerate(options['interfaces']):
            if (interface['vlan'] is not None):
                net_str = 'virtio=%s,bridge=vmbr%s' % (MACprettyprint(
                                                       randomMAC()),
                                                       interface['vlan'])
                mod_conf.append(('net%s' % i, net_str))
                logger.debug(mod_conf)
                if vm_name == 'masterdebian8':
                    interface['id'] = '%s%i' % \
                                      (cfg['VM_DEFAULTS8']['STARTNIC'],
                                       cfg['VM_DEFAULTS8']['STARTNICID']+i)
                else:
                    interface['id'] = '%s%i' % \
                                      (cfg['VM_DEFAULTS']['STARTNIC'],
                                       cfg['VM_DEFAULTS']['STARTNICID']+i)
                logger.debug(interface['id'])

        if 'disks' in options:
            for i, disk in enumerate(options['disks']):
                storage_str = '%s:%s,format=%s' % (storage, disk['size'],
                                                   disk['format'])
                mod_conf.append(('virtio%s' % str(i+1), storage_str))

        mod_conf.append(('memory', options['memory']))
        mod_conf.append(('cores', options['cores']))
        mod_conf.append(('sockets', options['sockets']))
        logger.debug(mod_conf)

        if not readonly:
            check_proxmox_response(proxmox_api.setVirtualMachineOptions
                                   (target_node, newid, mod_conf))
        logger.info('options settings')

        newimage = 'vm-%s-disk-1.raw' % newid
        src = '%s/%s/images/%s/%s' % (cfg['IMAGES_BASEPATH'], storage, newid,
                                      newimage)
        logger.debug(src)
        dst = '%s/%s' % (cfg['WORKING_MNT'], newid)
        logger.debug(dst)
        logger.debug(proxmox_api.getVirtualConfig(target_node, newid))

        # customize new vm os settings by rawinit
        if options['init']:
            rawinit.rawinit(cfg, options, src, dst, readonly=readonly,
                            log_level=cli_options.log_level)

        # finally start the new vm
        if not readonly:
            check_proxmox_response(proxmox_api.startVirtualMachine(
                                   target_node, newid))
        logger.info('starting the vm %s (id %s) on node %s' %
                    (name, newid, target_node))
    else:
        logger.error('unable to found template %s' % (vm_name))
        sys.exit(2)
