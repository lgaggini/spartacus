#! /usr/bin/env python

from settings.settings import PROXMOX, SSH_HOST_KEY, DEV, TMP_DIR, STATIC_DIR
from settings.settings import TEMPLATE_MAP, WORKING_MNT
from paramiko import SSHClient, WarningPolicy
from paramiko import RSAKey, ECDSAKey
from jinja2 import Environment, FileSystemLoader
import sys
import logging
import argparse
import coloredlogs
import subprocess

logger = logging.getLogger('rawinit')


def log_init():
    FORMAT = '%(asctime)s %(levelname)s %(module)s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    coloredlogs.install(level='INFO')


def template_compile(configs):
    env = Environment(loader=FileSystemLoader('templates'))

    custom_tmp_fd = '%s/%s' % (TMP_DIR, configs['name'])
    try:
        subprocess.call(['mkdir', '-p', custom_tmp_fd])
    except subprocess.CalledProcessError, ex:
        logger.error('error creating the folder %s: %s' % (custom_tmp_fd,
                                                           ex.output))
        sys.exit('exiting')

    for config_key in TEMPLATE_MAP.keys():
        j2_template = env.get_template('%s.j2' % config_key)
        with open('%s/%s' % (custom_tmp_fd, config_key), 'w') as config_file:
            var = configs[TEMPLATE_MAP[config_key]]
            config_file.write(j2_template.render(var=var))


def get_proxmox_ssh(proxmox):
    logger.info('opening connection to %s' % proxmox['SSH_HOST'])
    proxmox_ssh = SSHClient()
    proxmox_ssh.set_missing_host_key_policy(WarningPolicy())
    proxmox_ssh.connect(proxmox['SSH_HOST'],
                        username=proxmox['USER'].split('@')[0])
    return proxmox_ssh


def remote_command(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    stdout_str = ' ,'.join(stdout.readlines())
    stderr_str = ' ,'.join(stderr.readlines())
    logger.debug('stdout: ' + stdout_str)
    logger.debug('stderr: ' + stderr_str)
    return stdout.channel.recv_exit_status(), stdout_str, stderr_str


def check_exit(exit, stdout, stderr, block=True):
    if exit == 0:
        return
    else:
        logger.error(stderr)
        if block:
            sys.exit(127)


def nbd_module(ssh):
    """ load the nbd kernel module """
    logger.info('modprobe of nbd module')
    command = 'sudo modprobe nbd'
    return remote_command(ssh, command)


def image_mount(ssh, dev, src, dst, part):
    """ create a custom mountpoint and mount a qemu
    supported image by nbd """
    command = 'sudo qemu-nbd -f raw -c %s %s' % (dev, src)
    exit, stdout, stderr = remote_command(ssh, command)
    if (exit == 0):
        command = 'mkdir -p %s' % dst
        exit, stdout, stderr = remote_command(ssh, command)
        if (exit == 0):
            src_nbd = '%sp%s' % (dev, part)
            command = 'sudo mount %s %s' % (src_nbd, dst)
            return remote_command(ssh, command)
        else:
            return 127, stdout, stderr
    else:
        return 127, stdout, stderr


def image_umount(ssh, dev, src, dst):
    """ umount a qemu mounted image by nbd
    and remove custom mountpoint """
    double_check_path(dst, WORKING_MNT)
    command = 'sudo umount %s' % dst
    exit, stdout, stderr = remote_command(ssh, command)
    if (exit == 0):
        command = 'rmdir %s' % dst
        exit, stdout, stderr = remote_command(ssh, command)
        if (exit == 0):
            command = 'sudo qemu-nbd -d %s' % (dev)
            return remote_command(ssh, command)
        else:
            return 127, stdout, stderr
    else:
        return 127, stdout, stderr


def check_mount(ssh, dev, src, dst):
    """ check if the target mount is mounted """
    command = 'mount | grep -q %s' % dst
    exit, stdout, stderr = remote_command(ssh, command)
    if exit == 0:
        logger.debug('%s is just mounted' % dst)
        return True
    else:
        logger.debug('%s is not mounted' % dst)
        return False


def ssh_folder_init(ssh, dst):
    """ create and set permission for the user .ssh folder """
    cmd = 'mkdir -p %s/root/.ssh && chmod 0700 %s/root/.ssh' % (dst,
                                                                dst)
    exit, stdout, stderr = remote_command(ssh, cmd)


def deploy(ssh, src, dst, priv_key=False, pub_key=False):
    """ deploys the src file on dst wit some special managemente for
    ssh keys """
    logger.info('deploy %s to %s' % (src, dst))
    if(not double_check_path(dst, WORKING_MNT)):
        return
    try:
        proxmox_sftp = ssh.open_sftp()
    except Exception, ex:
        logger.error('SFTP exception: ' + str(ex))
        sys.exit('exiting')

    try:
        proxmox_sftp.put(src, dst)
        if priv_key:
            proxmox_sftp.chmod(dst, 0600)
        elif pub_key:
            proxmox_sftp.chmod(dst, 0644)

    except Exception, ex:
        logger.error('SFTP exception: ' + str(ex))

    proxmox_sftp.close()
    logger.info('verify the deployed file')
    command = 'sudo ls -l %s' % (dst)
    check_exit(*remote_command(ssh, command), block=False)


def generate_ssh_hostkeys(filename):
    """ generate RSA host keys """
    prv = RSAKey.generate(bits=2048, progress_func=None)
    prv.write_private_key_file(filename=filename)
    pub = RSAKey(filename=filename)
    with open('%s.pub' % filename, 'w') as f:
        f.write('%s %s' % (pub.get_name(), pub.get_base64()))


def double_check_hostname(ssh, dst, expected):
    """ check if the hostname of the mounted images is consistent """
    command = 'cat %s/etc/hostname' % dst
    exit, hostname, stderr = remote_command(ssh, command)
    check_exit(exit, hostname, stderr)
    if hostname.strip() != expected:
        logger.error('the mount image on %s doesnt have the expected hostname'
                     % dst)
        logger.error('expected: %s, found: %s' % (expected, hostname))
        return False
    else:
        return True


def double_check_path(dst, mnt):
    """ check if destination path is on the expected mountpoint to
    prevent deploy on the host """
    if mnt not in dst:
        logger.error('trying to deploy on %s, out of the mountpoint %s'
                     % (dst, mnt))
        return False
    else:
        return True


def rawinit(configs, src, dst, dev=DEV, part='1'):
    log_init()
    template_compile(configs)
    try:
        proxmox_ssh = get_proxmox_ssh(PROXMOX)
    except Exception, ex:
        logger.error('SSH exception: ' + str(ex))
        sys.exit('exiting')

    logger.info('modprobing of nbd module')
    check_exit(*nbd_module(proxmox_ssh))
    logger.info("nbd module modprobed")
    if check_mount(proxmox_ssh, dev, src, dst):
        logger.info('mountpoint %s busy, unmounting it' % dst)
        image_umount(proxmox_ssh, dev, src, dst)
    logger.info('mounting %s to %s by %s' % (src, dst, dev))
    check_exit(*image_mount(proxmox_ssh, dev, src, dst, part))
    logger.info('image %s mounted to %s by %sp%s' % (src, dst, dev, part))
    if (not double_check_hostname(proxmox_ssh, dst, configs['template'])):
        check_exit(*image_umount(proxmox_ssh, dev, src, dst))
    logger.info('deploy configurations')
    custom_tmp_fd = '%s/%s' % (TMP_DIR, configs['name'])
    deploy(proxmox_ssh, '%s/interfaces' % custom_tmp_fd,
           '%s/etc/network/interfaces' % dst)
    deploy(proxmox_ssh, '%s/hostname' % custom_tmp_fd, '%s/etc/hostname' % dst)
    deploy(proxmox_ssh, '%s/serverfarm' % custom_tmp_fd,
           '%s/etc/serverfarm' % dst)
    deploy(proxmox_ssh, '%s/pupuppetenvironment' % custom_tmp_fd,
           '%s/etc/pupuppetenvironment' % dst)
    deploy(proxmox_ssh, '%s/hosts' % custom_tmp_fd, '%s/etc/hosts' % dst)
    deploy(proxmox_ssh, '%s/puppet.conf' % custom_tmp_fd,
           '%s/etc/puppet/puppet.conf' % dst)
    logger.info('generate and deploy tmp RSA 2048 bit host keys')
    generate_ssh_hostkeys('%s/%s' % (custom_tmp_fd, SSH_HOST_KEY))
    logger.info('generated tmp RSA 2048 bit host keys for first ssh access')
    priv = '%s' % SSH_HOST_KEY
    pub = '%s.pub' % SSH_HOST_KEY
    deploy(proxmox_ssh, '%s/%s' % (custom_tmp_fd, priv), '%s/etc/ssh/%s'
           % (dst, priv), priv_key=True)
    deploy(proxmox_ssh, '%s/%s' % (custom_tmp_fd, pub), '%s/etc/ssh/%s'
           % (dst, pub), pub_key=True)
    logger.info('creating the root .ssh folder')
    ssh_folder_init(proxmox_ssh, dst)
    deploy(proxmox_ssh, '%s/authorized_keys' % STATIC_DIR,
           '%s/root/.ssh/authorized_keys' % dst, priv_key=True)
    logger.info('config deployed')
    logger.info('unmounting of %s to %s by %s' % (src, dst, dev))
    check_exit(*image_umount(proxmox_ssh, dev, src, dst))
    logger.info('image %s unmounted from %s by %s' % (src, dst, dev))
    logger.info('closing connection to %s' % PROXMOX['SSH_HOST'])
    proxmox_ssh.close()
    logger.info('connection to %s closed' % PROXMOX['SSH_HOST'])


if __name__ == '__main__':

    description = 'rawinit, customize a debian kvm disk image'
    parser = argparse.ArgumentParser(description=description)

    # TODO: read config from cli or other sources for standalone
    # usage

    configs = {
        'name': 'myvm1',
        'farm': 'farm1',
        'env': 'base',
        'interfaces': [
            {
                'vlan': '116',
                'auto': True,
                'hotplug': True,
                'ipaddress': '172.20.16.20',
                'netmask': '255.255.248.0',
                'gateway': '172.20.16.1'
            }
        ],
        'hosts': [
            {
                'ipaddress': '127.0.0.1',
                'name': 'myvm1.domain.com',
                'alias': 'myvm1'
            }
        ]
    }

    parser.add_argument('-s', '--source', required=True,
                        help='the source image to customize')
    parser.add_argument('-t', '--target', required=True,
                        help='the mount point to use for customization')

    cli_options = parser.parse_args()
    rawinit(configs, cli_options.source, cli_options.target)

    sys.exit(0)
