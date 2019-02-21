# spartacus

spartacus is a python tool to create a virtual machine on a proxmox cluster cloning an existent kvm virtual machine or
template and perform a debian/centos starting configuration by rawinit (based on qemu-nbd).
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
You can also put an authorized_keys file in the static folder to have them deployed for root user.

## Usage

You can use spartacus ~~passing arguments by command line or~~ in an infrastructure as a code pattern (the preferred way) by passing
a yaml file by the `-i/--inventory flag`.
It's now also possible to invoke directly rawinit to customize a just present vm.
The yaml inventory file is validated against a yaml schema.
In the `hostbooks` directory you can find an example host book.

### spartacus
```bash
usage: spartacus.py [-h] [-s SETTINGS] -i INVENTORY [-n] [-r]
                    [-l {debug,info,warning,error,critical}]

spartacus, deploy vm on proxmox cluster

optional arguments:
  -h, --help            show this help message and exit
  -s SETTINGS, --settings SETTINGS
                        custom settings file in settings package
  -i INVENTORY, --inventory INVENTORY
                        Yaml file path to read
  -n, --no-rawinit      disable the rawinit component (default enabled)
  -r, --readonly        readonly mode for debug (default disabled)
  -l {debug,info,warning,error,critical}, --log-level {debug,info,warning,error,critical}
                        log level (default info)
```

## rawinit
```bash
usage: rawinit.py [-h] [--settings SETTINGS] -s SOURCE -t TARGET -i INVENTORY                                                                                                                                      
                  [-r] [-l {debug,info,warning,error,critical}]

rawinit, customize a debian/centos kvm disk image

optional arguments:
  -h, --help            show this help message and exit
  --settings SETTINGS   custom settings file in settings package
  -s SOURCE, --source SOURCE
                        the source id image to customize
  -t TARGET, --target TARGET
                        the mount point to use for customization
  -i INVENTORY, --inventory INVENTORY
                        Yaml file path to read
  -r, --readonly        readonly mode for debug (default disabled)
  -l {debug,info,warning,error,critical}, --log-level {debug,info,warning,error,critical}
                        log level (default info)
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
    'node': {'type': 'string', 'default': 'auto',
             'allowed': self.resources['NODES']},
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
node: 'auto'
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
