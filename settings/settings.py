# general settings
SSH_HOST_KEY = 'ssh_host_rsa_key'
DEV = '/dev/nbd0'

# proxmox settings
proxmox = {}

proxmox['host'] = 'localhost'
proxmox['ssh_host'] = 'localhost'
proxmox['user'] = 'root'
proxmox['password'] = 'your_proxmox_password'
proxmox['images'] = '/var/lib/vz/images/'
proxmox['verify_ssl'] = False
proxmox['node'] = 'proxmox'
