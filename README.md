# spartacus

spartacus is a python tool to create a virtual machine on a proxmox cluster cloning an existent kvm virtual machine or
template and perform a debian starting configuration by rawinit (based on qemu-nbd):

* hostname
* network
* hosts
* puppet
* RSA ssh host key
* admin authorized keys
    * serverfarm
    * environment

## Requirements
```
pip install -r requirements.txt
```

## Configuration
Before use you have to configure settings in settings/settings.py. At least you have to configure PROXMOX dict for endpoint and
authorization configuration. You can configure also application local path and virtual machine creation defaults and availabe choices
(e.g. ram sizes, core and socket available)

## Usage

You can use spartacus passing arguments by command line or in an infrastructure as a code pattern you can pass arguments by a yaml file.
The yaml inventory file is validated against a yaml schema.

```
usage: spartacus.py [-h] [-t TEMPLATE] [--templateid TEMPLATEID] [-n NAME]
                    [-i INVENTORY] [-d DESCRIPTION] [--vlan {6,116}] [--auto]
                    [--hot] [--ipaddress IPADDRESS] [--netmask NETMASK]
                    [--gateway GATEWAY] [-m {128,256,512,1024,2048,4096,8192}]
                    [-c {1,2,4,8,16}] [-s {1,2,4,8,16}]
                    [-f {farm1,farm2,farm3}]
                    [-e ENV]

spartacus, deploy vm on proxmox cluster

optional arguments:
  -h, --help            show this help message and exit
  -t TEMPLATE, --template TEMPLATE
                        Name of template to clone (default masterdebian9)
  --templateid TEMPLATEID
                        id of the template to clone (default 694)
  -n NAME, --name NAME  Name of new virtual machines
  -i INVENTORY, --inventory INVENTORY
                        Yaml file path to read
  -d DESCRIPTION, --description DESCRIPTION
                        description for new vm
  --vlan {6,116}, --net {6,116}
                        vlan for the first interface
  --auto                allow auto for the first interface
  --hot                 allow hotplug for the first interface
  --ipaddress IPADDRESS
                        first interface ip address
  --netmask NETMASK     first interface netmask
  --gateway GATEWAY     first interface gateway
  -m {128,256,512,1024,2048,4096,8192}, --memory {128,256,512,1024,2048,4096,8192}
                        MB of ram to be allocated (default 4096)
  -c {1,2,4,8,16}, --cores {1,2,4,8,16}
                        # of cores (default 2)
  -s {1,2,4,8,16}, --sockets {1,2,4,8,16}
                        # of socket (default 2)
  -f {farm1,farm2,farm3}, --farm {farm1,farm2,farm3}
                        farm for puppet
  -e ENV, --env ENV     environment for puppet
```

## Inventory schema
```
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

vm_schema = {
    'template': {'type': 'string', 'default': VM_DEFAULTS['TEMPLATE']},
    'templateid': {'type': 'string', 'default': VM_DEFAULTS['TEMPLATEID']},
    'name': {'required': True, 'type': 'string'},
    'description': {'type': 'string'},
    'hosts': hosts_schema,
    'sockets': {'type': 'string', 'allowed': VM_RESOURCES['SOCKETS'],
                'default': VM_DEFAULTS['SOCKETS']},
    'cores': {'type': 'string', 'allowed': VM_RESOURCES['CORES'],
              'default': VM_DEFAULTS['CORES']},
    'memory': {'type': 'string', 'allowed': VM_RESOURCES['RAM'],
               'default': VM_DEFAULTS['RAM']},
    'interfaces': interfaces_schema,
    'farm':  {'type': 'string', 'allowed': VM_RESOURCES['FARMS'],
              'default': VM_DEFAULTS['FARM']},
    'env':  {'type': 'string'}
}
```

## Inventory example
```
---$                                                                                                                                                                                                                
template: masterdebian9
name: spartacus01
description: spartacus01
hosts:
    - ipaddress: 172.20.16.110
      name: spartacus01.domain
      alias: spartacus01
sockets: '2'
cores: '2'
memory: '4096'
interfaces:
    - vlan: '116'
      auto: True
      hotplug: True
      ipaddress: 172.20.16.110
      netmask: 255.255.248.0
      gateway: 172.20.16.1
farm: farm1
env: base
```
