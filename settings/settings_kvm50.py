# general settings
SSH_HOST_KEY = 'ssh_host_rsa_key'
DEV = '/dev/nbd0'
WORKING_DIR = '.'
WORKING_MNT = '/mnt/spartacus'
TMP_DIR = '%s/generated' % WORKING_DIR
STATIC_DIR = '%s/static' % WORKING_DIR
IMAGES_BASEPATH = '/mnt/pve'

# vm options available
VM_RESOURCES = {
    'VLANS': ['6', '114', '116'],
    'RAM': ['128', '256', '512', '1024', '2048', '4096'],
    'CORES': ['1', '2', '4', '8', '16'],
    'SOCKETS': ['1', '2', '4', '8', '16'],
    'FARMS': ['farm1', 'farm2', 'farm3']
}

# kvm resources thresolds
KVM_THRES = {
    'SPACE': 100000000000,
    'MAGIC': 40,
    'MEMORY': 8192,
}

# vm defaults
VM_DEFAULTS = {
    'ODD_VOL': 'pvetest',
    'EVEN_VOL': 'pvetest',
    'TEMPLATE': 'masterdebian9',
    'TEMPLATEID': '100',
    'CORES': '2',
    'SOCKETS': '2',
    'RAM': '4096',
    'FARM': 'farm1',
    'STARTNIC': 'ens',
    'STARTNICID': 18
}

# proxmox settings
PROXMOX = {
    'HOST': 'kvm.domain',
    'SSH_HOST': 'kvm.domain',
    'USER': 'root@pam',
    'PASSWORD': 'password'
}

# templating settings
TEMPLATE_MAP = {
    'hostname': 'name',
    'interfaces': 'interfaces',
    'hosts': 'hosts',
    'puppet.conf': 'env',
    'pu_puppetenvironment': 'env',
    'serverfarm': 'farm'
}
