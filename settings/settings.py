# general settings
SSH_HOST_KEY = 'ssh_host_rsa_key'
DEV = '/dev/nbd0'
WORKING_DIR = '.'
TMP_DIR = '%s/generated' % WORKING_DIR
STATIC_DIR = '%s/static' % WORKING_DIR
AVAILABLE_VLANS = ['6', '116']
RAM_SIZES = ['128', '256', '512', '1024', '2048', '4096']
CORE_SIZES = ['1', '2', '4', '8', '16']
SOCKET_SIZES =  ['1', '2', '4', '8', '16']
AVAILABLE_FARMS = ['farm1', 'farm2', 'farm3']

# proxmox settings
proxmox = {}

proxmox['host'] = 'localhost'
proxmox['ssh_host'] = 'localhost'
proxmox['user'] = 'root'
proxmox['password'] = 'your_proxmox_password'
proxmox['images'] = '/var/lib/vz/images/'
proxmox['verify_ssl'] = False
proxmox['node'] = 'proxmox'
