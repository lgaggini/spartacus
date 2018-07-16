#! /usr/bin/env python

from settings.settings import VM_RESOURCES, VM_DEFAULTS

from cerberus import Validator
import socket

hosts_schema = {
    'type': 'list',
    'minlength': 1,
    'schema': {
        'type': 'dict',
        'schema': {
            'ipaddress': {
                'type': 'ipaddress'
            },
            'name': {
                'type': 'string',
                'dependencies': 'ipaddress'
            },
            'alias': {
                'type': 'string',
                'dependencies': ['ipaddress', 'name']
            },
        }
    }
}

interfaces_schema = {
    'type': 'list',
    'minlength': 1,
    'schema': {
        'type': 'dict',
        'schema': {
            'vlan': {
                'type': 'string', 'allowed': VM_RESOURCES['VLANS']
            },
            'auto': {
                'type': 'boolean', 'default': False
            },
            'hotplug': {
                'type': 'boolean', 'default': False
            },
            'ipaddress': {
                'type': 'ipaddress',
                'dependencies': ['netmask', 'vlan']
            },
            'netmask': {
                'type': 'netmask',
                'dependencies': ['ipaddress']
            },
            'gateway': {
                'type': 'ipaddress',
                'dependencies': ['ipaddress', 'netmask']
            },
        }
    }
}

disks_schema = {
    'type': 'list',
    'minlength': 0,
    'schema': {
        'type': 'dict',
        'schema': {
            'size': {
                'type': 'string', 'allowed': VM_RESOURCES['DISKSIZES']
            },
            'format': {
                'type': 'string', 'allowed': VM_RESOURCES['DISKFORMATS']
            },
        }
    }
}

vm_schema = {
    'template': {'type': 'string', 'default': VM_DEFAULTS['TEMPLATE']},
    'templateid': {'type': 'string', 'default': VM_DEFAULTS['TEMPLATEID']},
    'name': {'required': True, 'type': 'string'},
    'vmid': {'type': 'vmid', 'default': 'auto'},
    'description': {'type': 'string'},
    'hosts': hosts_schema,
    'sockets': {'type': 'string', 'allowed': VM_RESOURCES['SOCKETS'],
                'default': VM_DEFAULTS['SOCKETS']},
    'cores': {'type': 'string', 'allowed': VM_RESOURCES['CORES'],
              'default': VM_DEFAULTS['CORES']},
    'memory': {'type': 'string', 'allowed': VM_RESOURCES['RAM'],
               'default': VM_DEFAULTS['RAM']},
    'interfaces': interfaces_schema,
    'disks': disks_schema,
    'farm':  {'type': 'string', 'allowed': VM_RESOURCES['FARMS'],
              'default': VM_DEFAULTS['FARM']},
    'env':  {'type': 'string', 'default': VM_DEFAULTS['ENV']},
    'puppetmaster':  {'type': 'string', 'default': 'puppet.register.it'}
}


class VMDefValidator(Validator):
    def _validate_type_ipaddress(self, value):
        try:
            socket.inet_aton(value)
            return True
        except socket.error:
            return False

    def _validate_type_netmask(self, value):
        if not self._validate_type_ipaddress(value):
            return False
        netmask = value
        seen0 = False
        for x in netmask.split('.'):
            for c in bin(int(x))[2:]:
                if '1' == c:
                    if seen0:
                        return False
                else:
                    seen0 = True
        return True

    def _validate_type_vmid(self, value):
        if value == 'auto':
            return True
        elif int(value) < 10000:
            return True
        else:
            return False
