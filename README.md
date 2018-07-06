# spartacus

spartacus is a python tool to create a virtual machine on a proxmox cluster cloning an existent kvm virtual machine or
template and perform a debian starting configuration by rawinit (based on qemu-nbd).
It extends my old-project [proxmox-init](https://github.com/libersoft/proxmox-init) for my current environment (where cloudinit doesn't work yet).
It configures:

* hostname
* network
* hosts
* puppet
* RSA ssh host key
* admin authorized keys
* serverfarm
* environment

## Install
### Clone
```bash
git clone https://github.com/lgaggini/spartacus.git
```

### [Virtualenv](https://virtualenvwrapper.readthedocs.io/en/latest/command_ref.html) (strongly suggested but optional)
```bash
mkvirtualenv -a spartacus spartacus
```

### Requirements
```bash
pip install -r requirements.txt
```
For `pyproxmox` maybe the pip version is a bit outdated and you could need to get the updated version directly at
[github repo](https://github.com/Daemonthread/pyproxmox).
In the pip version the function `getClusterNodeList()` seems to be missing.

## Configuration
Before use you have to configure settings in `settings/settings.py` or you can have your custom settings file in settings package and
recall it with the `--setting flag`. At least you have to configure PROXMOX dict for endpoint and
authorization configuration. You can configure also application local path and virtual machine creation defaults and availabe choices
(e.g. ram sizes, core and socket available).
You can also double check the jinja templates in `templates` directory.

## Usage

You can use spartacus passing arguments by command line or in an infrastructure as a code pattern (the preferred way) by passing
a yaml file by the `-i/--inventory flag`.
The yaml inventory file is validated against a yaml schema.
In the `hostbooks` directory you can find an example host book.

```bash
usage: spartacus.py [-h] [--settings SETTINGS] [-i INVENTORY] [-n NAME]
                    [-d DESCRIPTION] [--vmid VMID] [--no-rawinit]
                    [-t TEMPLATE] [--templateid TEMPLATEID]
                    [--vlan {0,3,4,5,6,7,11,13,14,15,20,21,22,23,24,25,27,28,29,30,31,32,33,34,
                     36,37,38,39,40,42,43,44,45,46,47,48,49,50,51,52,53,54,56,57,58,59,60,61,63,
                     64,65,66,68,69,70,71,91,99,100,101,102,103,104,105,106,107,108,109,110,111,
                     112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,
                     131,132,133,134,135,136,137,138,139,140,141,153,172,183}]
                    [--auto] [--hot] [--ipaddress IPADDRESS]
                    [--netmask NETMASK] [--gateway GATEWAY]
                    [-m {128,256,512,1024,2048,4096,8192,16384,32768}]
                    [-c {1,2,4,8,16}] [-s {1,2,4,8,16}] [--fqdn FQDN]
                    [-f {farm1,farm2,farm3}]
                    [-e ENV]

spartacus, deploy vm on proxmox cluster

optional arguments:
  -h, --help            show this help message and exit
  --settings SETTINGS   custom settings file in settings package
  -i INVENTORY, --inventory INVENTORY
                        Yaml file path to read
  -n NAME, --name NAME  Name of new virtual machines
  -d DESCRIPTION, --description DESCRIPTION
                        description for new vm
  --vmid VMID           the vmid for the new vm
  --no-rawinit          disable the rawinit component (default enabled)
  -t TEMPLATE, --template TEMPLATE
                        Name of template to clone (default masterdebian9)
  --templateid TEMPLATEID
                        id of the template to clone (default 694)
  --vlan {0,3,4,5,6,7,11,13,14,15,20,21,22,23,24,25,27,28,29,30,31,32,33,34,36,37,38,39,40,42,
  43,44,45,46,47,48,49,50,51,52,53,54,56,57,58,59,60,61,63,64,65,66,68,69,70,71,91,99,100,101,
  102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,
  125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,153,172,183}, --net {0,3,
  4,5,6,7,11,13,14,15,20,21,22,23,24,25,27,28,29,30,31,32,33,34,36,37,38,39,40,42,43,44,45,46,47,
  48,49,50,51,52,53,54,56,57,58,59,60,61,63,64,65,66,68,69,70,71,91,99,100,101,102,103,104,105,
  106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,
  129,130,131,132,133,134,135,136,137,138,139,140,141,153,172,183}
                        vlan for the first interface
  --auto                allow auto for the first interface
  --hot                 allow hotplug for the first interface
  --ipaddress IPADDRESS
                        first interface ip address
  --netmask NETMASK     first interface netmask
  --gateway GATEWAY     first interface gateway
  -m {128,256,512,1024,2048,4096,8192,16384,32768}, --memory {128,256,512,1024,2048,4096,8192,16384,32768}
                        MB of ram to be allocated (default 4096)
  -c {1,2,4,8,16}, --cores {1,2,4,8,16}
                        # of cores (default 2)
  -s {1,2,4,8,16}, --sockets {1,2,4,8,16}
                        # of socket (default 2)
  --fqdn FQDN           fqdn for hosts file
  -f {farm1,farm2,farm3}, --farm {farm1,farm2,farm3}
                        farm for puppet
  -e ENV, --env ENV     environment for puppet

```

## Inventory schema
```python
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
    'vmid': {'type': 'string', 'default': 'auto'},
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
    'puppetmaster':  {'type': 'string', 'default': 'puppetmaster.domain'}
}
```

## Inventory example
```yml
---$                                                                                                                                                                                                                
template: masterdebian9
name: spartacus01
vmid: '101'
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
disks:
    - size: '1'
      format: 'raw'
env: base
puppetmaster: puppetmaster.domain
```
