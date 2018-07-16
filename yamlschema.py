#! /usr/bin/env python


from cerberus import Validator
import socket


class YamlSchema:
    defaults = {}
    resources = {}
    hosts_schema = {}
    interfaces_schema = {}
    disks_schema = {}
    vm_schema = {}

    def __init__(self, defaults, resources):
        self.defaults = defaults
        self.resources = resources
        self.hosts_schema = {
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
        self.interfaces_schema = {
            'type': 'list',
            'minlength': 1,
            'schema': {
                'type': 'dict',
                'schema': {
                    'vlan': {
                        'type': 'string', 'allowed': self.resources['VLANS']
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
        self.disks_schema = {
            'type': 'list',
            'minlength': 0,
            'schema': {
                'type': 'dict',
                'schema': {
                    'size': {
                        'type': 'string',
                        'allowed': self.resources['DISKSIZES']
                    },
                    'format': {
                        'type': 'string',
                        'allowed': self.resources['DISKFORMATS']
                    },
                }
            }
        }
        self.vm_schema = {
            'template': {'type': 'string',
                         'default': self.defaults['TEMPLATE']},
            'templateid': {'type': 'string',
                           'default': self.defaults['TEMPLATEID']},
            'name': {'required': True, 'type': 'string'},
            'vmid': {'type': 'vmid', 'default': 'auto'},
            'description': {'type': 'string'},
            'hosts': self.hosts_schema,
            'sockets': {'type': 'string', 'allowed': self.resources['SOCKETS'],
                        'default': self.defaults['SOCKETS']},
            'cores': {'type': 'string', 'allowed': self.resources['CORES'],
                      'default': self.defaults['CORES']},
            'memory': {'type': 'string', 'allowed': self.resources['RAM'],
                       'default': self.defaults['RAM']},
            'interfaces': self.interfaces_schema,
            'disks': self.disks_schema,
            'farm':  {'type': 'string', 'allowed': self.resources['FARMS'],
                      'default': self.defaults['FARM']},
            'env':  {'type': 'string', 'default': self.defaults['ENV']},
            'puppetmaster':  {'type': 'string',
                              'default': 'puppet.register.it'}
        }

    def get_vm_schema(self):
        return self.vm_schema


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
