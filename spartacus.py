#! /usr/bin/env python
# documentazione api proxmox:
# https://pve.proxmox.com/pve-docs/api-viewer/index.html
# documentazione pyproxmox:
# https://github.com/Daemonthread/pyproxmox

import pyproxmox
import time
from optparse import OptionParser
import sys
import random


def print_data(msg):
    print (time.strftime("%H:%M:%S")+" "+msg)


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
        # print s['content']
        if s['active'] == 1 and s['content'].find("images") == 0 and s['storage'].find("pve") == 0:
            stor = s['storage']
            dati = b.getNodeStorageStatus('kvm', stor)['data']
            # print dati
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
        # print "%s %s %s %s %s %s %s" % (n,cpu1,cpu5,totram, freeram,percram,magic)
        d[n] = magic

        for w in sorted(d, key=d.get, reverse=True):
            if d[w] >= 40:
                return w
    return None


class ScriptParser(OptionParser):
    def format_epilog(self, formatter):
        return self.epilog


if __name__ == '__main__':

    parser = ScriptParser(epilog=
                          """
                          Examples:
                          """+sys.argv[0]+""" -t masterdebian8 -n test   # Clona la macchina masterdebian8 e la chiama test
                          """+sys.argv[0]+""" -t masterdebian8 -n test -0 6 -1 124   # Clona la macchina masterdebian8 e la chiama test con 2 interfacce di rete (eth0 in vlan 6 e eth1 in vlan 124)
                          """)

    parser.add_option("-t", "--template", dest="template", type="string", default=None, help="Name of template to clone")
    parser.add_option("-n", "--name", dest="name", type="string", default=None, help="Name of new virtual machine")
    parser.add_option("-0", "--net0", dest="net0", type="string", default=None, help="vlan of net0")
    parser.add_option("-1", "--net1", dest="net1", type="string", default=None, help="vlan of net1")
    parser.add_option("-m", "--memory", dest="memory", type="string", default=4096, help="MB of RAM (default 4096 MB)")
    parser.add_option("-c", "--core", dest="core", type="string", default=2, help="# of cores (default 2)")
    parser.add_option("-s", "--socket", dest="socket", type="string", default=2, help="# of sockets (default 2)")

    (options, args) = parser.parse_args()

    # argomenti obbligatori
    if (options.template is None or options.name is None):
        print('Error: --action must be show or delete or search or status')
        parser.print_help()
        sys.exit(1)

    print_data("mi connetto")
    a = prox_auth('kvm.domain', 'root@pam', 'password')
    b = pyproxmox(a)

    vm_name = options.template
    name = options.name
    print_data("cerco il template")
    vmid, node = findTemplate(b, vm_name)
    print_data("ho trovato il template")

    if (vmid is not None):
        # prende il primo id disponibile
        newid = b.getClusterVmNextId()['data']

        print_data("ho trovato il VmNextId")
        target_node = getAvailableNode(b)
        print_data("ho trovato il nodo disponibile")
        storage = getNFSVolume(b)
        print_data("ho trovato lo storage")

        # installa una macchina clonando il template
        install = [('newid',newid), ('name', name), ('full', 1),('format', 'raw'), ('storage', storage), ('target', target_node)]
        print("installo la macchina %s (id %s) clonando il template %s (id %s su macchina %s) sul nodo %s utilizzando lo storage %s" % (name,newid,vm_name,vmid,node,target_node,storage))
        b.cloneVirtualMachine(node, vmid, install)
        print_data("inizio la clonazione")

        while True:
            if b.getVirtualStatus(target_node, newid)['status']['ok'] is True:
                break
            # print "aspetto altri 5 secondi"
            time.sleep(5)

        print_data("finita la clonazione")
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
        print_data("setto le opzioni")
        # TODO: montare il volume della macchina e modificare hostname, hosts e conf di rete
        # print b.getVirtualConfig(target_node,newid)
        b.startVirtualMachine(target_node, newid)
        print_data("accendo la macchina")
    else:
        print ("impossibile trovare il template %s" % (vm_name))
        sys.exit(2)
