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
    'VLANS': ['0', '3', '4', '5', '6', '7', '11', '13', '14', '15', '20',
              '21', '22', '23', '24', '25', '27', '28', '29', '30', '31',
              '32', '33', '34', '36', '37', '38', '39', '40', '42', '43',
              '44', '45', '46', '47', '48', '49', '50', '51', '52', '53',
              '54', '56', '57', '58', '59', '60', '61', '63', '64', '65',
              '66', '68', '69', '70', '71', '91', '99', '100', '101', '102',
              '103', '104', '105', '106', '107', '108', '109', '110', '111',
              '112', '113', '114', '115', '116', '117', '118', '119', '120',
              '121', '122', '123', '124', '125', '126', '127', '128', '129',
              '130', '131', '132', '133', '134', '135', '136', '137', '138',
              '139', '140', '141', '153', '172', '183'],
    'RAM': ['128', '256', '512', '1024', '2048', '4096', '8192', '16384',
            '32768'],
    'DISKSIZES': ['1', '2', '5', '10', '20', '30', '40', '50', '100'],
    'DISKFORMATS': ['raw', 'qcow2'],
    'CORES': ['1', '2', '4', '8', '16'],
    'SOCKETS': ['1', '2', '4', '8', '16'],
    'FARMS': ['farm1', 'farm2', 'farm3'],
    'NODES': ['auto', 'kvm41', 'kvm42', 'kvm43', 'kvm44', 'kvm45',
              'kvm46', 'kvm47', 'kvm48', 'kvm49', 'kvm50']
}

# kvm resources thresolds
KVM_THRES = {
    'SPACE': 100000000000,
    'MAGIC': 40,
    'MEMORY': 8192,
}

# vm defaults
VM_DEFAULTS = {
    'ODD_VOL': ['pvetest'],
    'EVEN_VOL': ['pvetest'],
    'TEMPLATE': 'masterdebian9',
    'TEMPLATEID': '100',
    'TEMPLATENODE': 'kvm',
    'CORES': '2',
    'SOCKETS': '2',
    'RAM': '4096',
    'FARM': 'farm1',
    'STARTNIC': 'ens',
    'STARTNICID': 18
}

# vm defaults
VM_DEFAULTS8 = {
    'ODD_VOL': ['pvetest'],
    'EVEN_VOL': ['pvetest'],
    'TEMPLATE': 'masterdebian9',
    'TEMPLATEID': '100',
    'TEMPLATENODE': 'kvm',
    'CORES': '2',
    'SOCKETS': '2',
    'RAM': '4096',
    'FARM': 'farm1',
    'STARTNIC': 'eth',
    'STARTNICID': 0
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
