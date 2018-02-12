#! /usr/bin/env python

from settings.settings import DEFAULT_TEMPLATE, DEFAULT_TEMPLATEID
from settings.settings import AVAILABLE_VLANS, AVAILABLE_FARMS
from settings.settings import RAM_SIZES, CORE_SIZES, SOCKET_SIZES
from settings.settings import DEFAULT_SOCKETS, DEFAULT_CORES, DEFAULT_RAM
from settings.settings import DEFAULT_FARM
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

networks_schema = {
    'type': 'list',
    'minlength': 1,
    'schema': {
        'type': 'dict',
        'schema': {
            'vlan': {
                'type': 'string', 'allowed': AVAILABLE_VLANS
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
                'type': 'ipaddress',
                'dependencies': ['ipaddress']
            },
            'gateway': {
                'type': 'ipaddress',
                'dependencies': ['ipaddress', 'netmask']
            },
        }
    }
}

vm_schema = {
    'template': {'type': 'string', 'default': DEFAULT_TEMPLATE},
    'templateid': {'type': 'string', 'default': DEFAULT_TEMPLATEID},
    'name': {'required': True, 'type': 'string'},
    'description': {'type': 'string'},
    'hosts': hosts_schema,
    'sockets': {'type': 'string', 'allowed': SOCKET_SIZES,
                'default': DEFAULT_SOCKETS},
    'cores': {'type': 'string', 'allowed': CORE_SIZES,
              'default': DEFAULT_CORES},
    'memory': {'type': 'string', 'allowed': RAM_SIZES, 'default': DEFAULT_RAM},
    'networks': networks_schema,
    'farm':  {'type': 'string', 'allowed': AVAILABLE_FARMS,
              'default': DEFAULT_FARM},
    'env':  {'type': 'string'}
}


class VMDefValidator(Validator):
    def _validate_type_ipaddress(self, value):
        try:
            socket.inet_aton(value)
            return True
        except socket.error:
            return False
