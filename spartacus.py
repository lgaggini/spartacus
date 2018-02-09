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


def getNFSVolume(connessione):
    """prende il volume attivo pveXX con meno spazio utilizzato"""
    space_stor = {}
    storage = b.getNodeStorage('kvm')

    for s in storage['data']:
        logger.debug(s['content'])
        if s['active'] == 1 and s['content'].find("images") == 0 and \
           s['storage'].find("pve") == 0:
            stor = s['storage']
            dati = b.getNodeStorageStatus('kvm', stor)['data']
            logger.debug(dati)
            if dati['avail'] > 100000000:
                space_stor[stor] = dati['used']

    for w in sorted(space_stor, key=space_stor.get, reverse=False):
        return w
    return None


def findTemplate(connessione, vmname):
    """ dato il nome del template (vmname) ritorna """
    """ su quale nodo kvm si trova e qual e' l'id """
    """ se non trova niente ritorna None, None """
    nodes = connessione.getClusterNodeList()
    for node in nodes['data']:
        n = node['node']
        machines = connessione.getNodeVirtualIndex(n)
        for m in machines['data']:
            data = connessione.getVirtualConfig(n, m['vmid'])
            # if 'net0' in data['data']:
            #    print data['data']['net0']
            # if 'net1' in data['data']:
            #    print data['data']['net1']
        if (m['name'] == vmname):
            return m['vmid'], n
    return None, None


def getAvailableNode(connessione):
    """calcola qual e' la macchina piu' scarica"""
    d = {}
    nodes = connessione.getClusterNodeList()
    for node in nodes['data']:
        n = node['node']
        status = b.getNodeStatus(n)
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


def ip_address(ip_address):
    try:
        socket.inet_aton(ip_address)
        return ip_address
    except socket.error:
        raise argparse.ArgumentTypeError("%s is an invalid ip address"
                                         % ip_address)


if __name__ == '__main__':

    log_init()

    available_vlan = ['6', '116']
    ram_sizes = ['1024', '2048', '4096']
    core_sizes = ['1', '2', '4']
    socket_sizes = ['1', '2', '4']
    farm_availables = ['farm1']

    description = "spartacus, deploy vm on proxmox cluster"
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('-t', '--template', default='masterdebian9',
                        help='Name of template to clone \
                        (default masterdebian9)')
    parser.add_argument('-n', '--name', required=True,
                        help='Name of new virtual machines')
    parser.add_argument('-d', '--description', help='description for new vm')
    parser.add_argument('-0', '--net0', '--vlan0', choices=AVAILABLE_VLANS,
                        help='vlan for the first interface')
    parser.add_argument('--auto0', action='store_true',
                        help='allow auto for the first interface')
    parser.add_argument('--hot0', action='store_true',
                        help='allow hotplug for the first interface')
    parser.add_argument('--ipaddres0', type=ip_address,
                        help='first interface ip address')
    parser.add_argument('--network0', type=ip_address,
                        help='first interface network')
    parser.add_argument('--gateway0', type=ip_address,
                        help='first interface gateway')
    parser.add_argument('-m', '--memory', default='4096', choices=RAM_SIZES,
                        help='MB of ram to be allocated (default 4096)')
    parser.add_argument('-c', '--core', default='2', choices=CORE_SIZES,
                        help='# of cores (default 2)')
    parser.add_argument('-s', '--socket', default='2', choices=SOCKET_SIZES,
                        help='# of socket (default 2)')
    parser.add_argument('-f', '--farm', default='farm1',
                        choices=AVAILABLE_FARMS, help='farm for puppet')
    parser.add_argument('-e', '--env', help='environment for puppet')

    options = parser.parse_args()
    logger.debug(options.template)


    sys.exit(0)

    logger.info("mi connetto")
    a = prox_auth('kvm.domain', 'root@pam', 'password')
    b = pyproxmox(a)

    vm_name = options.template
    name = options.name
    logger.info("cerco il template")
    vmid, node = findTemplate(b, vm_name)
    logger.info("ho trovato il template")

    if (vmid is not None):
        # prende il primo id disponibile
        newid = b.getClusterVmNextId()['data']

        logger.info("ho trovato il VmNextId")
        target_node = getAvailableNode(b)
        logger.info("ho trovato il nodo disponibile")
        storage = getNFSVolume(b)
        logger.info("ho trovato lo storage")

        # installa una macchina clonando il template
        install = [('newid', newid), ('name', name), ('full', 1),
                   ('format', 'raw'), ('storage', storage),
                   ('target', target_node)]
        logger.info("installo la macchina %s (id %s) clonando il template %s \
                    (id %s su macchina %s) sul nodo %s utilizzando lo storage \
                    %s" % (name, newid, vm_name, vmid, node, target_node,
                    storage))
        b.cloneVirtualMachine(node, vmid, install)
        logger.info("inizio la clonazione")

        while True:
            if b.getVirtualStatus(target_node, newid)['status']['ok'] is True:
                break
            logger.info("aspetto altri 5 secondi")
            time.sleep(5)

        logger.info("finita la clonazione")
        # config = b.getVirtualConfig(target_node,newid)['data']['net0']
        mod_conf = []
        if (options.net0 is not None):
            str = 'virtio='+MACprettyprint(randomMAC())+',bridge=vmbr'+options.net0
            mod_conf.append(('net0', str))
        if (options.net1 is not None):
            str = 'virtio='+MACprettyprint(randomMAC())+',bridge=vmbr'+options.net1
            mod_conf.append(('net1', str))
        mod_conf.append(('memory', options.memory))
        mod_conf.append(('cores', options.core))
        mod_conf.append(('sockets', options.socket))
        # print mod_conf
        b.setVirtualMachineOptions(target_node, newid, mod_conf)
        logger.info("setto le opzioni")
        # TODO: montare il volume della macchina e modificare hostname,
        # hosts e conf di rete
        logger.debug(b.getVirtualConfig(target_node, newid))
        b.startVirtualMachine(target_node, newid)
        logger.info("accendo la macchina")
    else:
        logger.error("impossibile trovare il template %s" % (vm_name))
        sys.exit(2)
