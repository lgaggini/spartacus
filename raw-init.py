#! /usr/bin/env python

from settings.settings import proxmox, SSH_HOST_KEY, DEV, TMP_DIR, STATIC_DIR
from paramiko import SSHClient, WarningPolicy
from paramiko import RSAKey, ECDSAKey
from jinja2 import Environment, FileSystemLoader
import sys
import logging
import argparse


configs = {}
configs['hostname'] = 'hostname'
configs['interfaces'] = [{'vlan': '6', 'id': 'ens18', 'auto': True,
                          'hotplug': True,
                          'address': '192.168.0.15',
                          'netmask': '255.255.248.0',
                          'gateway': '192.168.0.1'}]
configs['hosts'] = [{'ip_address': '192.168.0.15', 'fqdn': 'me.me',
                     'alias': 'me'}]
configs['pupuppetenvironment'] = 'base'
configs['serverfarm'] = 'farm1'
configs['puppet.conf'] = 'base'

src = '/home/lg/tmp/zesty-server-cloudimg-amd64.img'
dst = '/mnt/vm_image'

logger = logging.getLogger(__file__)


def log_init():
    FORMAT = '%(asctime)s %(levelname)s %(module)s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)


def template_compile(configs):
    env = Environment(loader=FileSystemLoader('templates'))

    config_keys = ['hostname', 'interfaces', 'hosts', 'puppet.conf',
                   'pupuppetenvironment', 'serverfarm']

    for config_key in config_keys:
        j2_template = env.get_template('%s.j2' % config_key)
        with open('%s/%s' % (TMP_DIR, config_key), 'w') as config_file:
            config_file.write(j2_template.render(var=configs[config_key]))


def get_proxmox_ssh(proxmox):
    logging.info('opening connection to %s' % proxmox['host'])
    proxmox_ssh = SSHClient()
    proxmox_ssh.set_missing_host_key_policy(WarningPolicy())
    proxmox_ssh.connect(proxmox['ssh_host'],
                        username=proxmox['user'].split('@')[0])
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
    logger.info('modprobe of nbd module')
    command = 'sudo modprobe nbd'
    return remote_command(ssh, command)


def image_mount(ssh, dev, src, dst, part):
    command = 'sudo qemu-nbd -c %s %s' % (dev, src)
    exit, stdout, stderr = remote_command(ssh, command)
    if (exit == 0):
        src_nbd = '%sp%s' % (dev, part)
        command = 'sudo mount %s %s' % (src_nbd, dst)
        return remote_command(ssh, command)
    else:
        return 127, stdout, stderr


def image_umount(ssh, dev, src, dst):
    command = 'sudo umount %s' % dst
    exit, stdout, stderr = remote_command(ssh, command)
    if (exit == 0):
        command = 'sudo qemu-nbd -d %s' % (dev)
        return remote_command(ssh, command)
    else:
        return 127, stdout, stderr


def deploy(ssh, src, dst, priv_key=False, pub_key=False):
    logging.info('deploy %s to %s' % (src, dst))
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
    logging.info('verify the deployed file')
    command = 'sudo ls -l %s' % (dst)
    check_exit(*remote_command(ssh, command), block=False)


def generate_ssh_hostkeys(filename):
    prv = RSAKey.generate(bits=2048, progress_func=None)
    prv.write_private_key_file(filename=filename)
    pub = RSAKey(filename=filename)
    with open('%s.pub' % filename, 'w') as f:
        f.write('%s %s' % (pub.get_name(), pub.get_base64()))


def raw_init(configs, src, dst, dev=DEV, part='1'):
    log_init()
    template_compile(configs)
    try:
        proxmox_ssh = get_proxmox_ssh(proxmox)
    except Exception, ex:
        logger.error('SSH exception: ' + str(ex))
        sys.exit('exiting')

    logger.info('Modprobing of nbd module')
    check_exit(*nbd_module(proxmox_ssh))
    logger.info("nbd module modprobed")
    logger.info('Mounting %s to %s by %s' % (src, dst, dev))
    check_exit(*image_mount(proxmox_ssh, dev, src, dst, part))
    logger.info('Image %s mounted to %s by %sp%s' % (src, dst, dev, part))
    logger.info('Deploy configurations')
    deploy(proxmox_ssh, '%s/interfaces' % TMP_DIR, '%s/etc/network/interfaces'
           % dst)
    deploy(proxmox_ssh, '%s/hostname' % TMP_DIR, '%s/etc/hostname' % dst)
    deploy(proxmox_ssh, '%s/serverfarm' % TMP_DIR, '%s/etc/serverfarm' % dst)
    deploy(proxmox_ssh, '%s/pupuppetenvironment' % TMP_DIR,
           '%s/etc/pupuppetenvironment' % dst)
    deploy(proxmox_ssh, '%s/hosts' % TMP_DIR, '%s/etc/hosts' % dst)
    deploy(proxmox_ssh, '%s/puppet.conf' % TMP_DIR,
           '%s/etc/puppet/puppet.conf' % dst)
    logger.info('Generate and deploy tmp RSA 2048 bit host keys for \
                first ssh access')
    generate_ssh_hostkeys('%s/%s' % (TMP_DIR, SSH_HOST_KEY))
    logger.info('Generated tmp RSA 2048 bit host keys for first ssh access')
    priv = '%s' % SSH_HOST_KEY
    pub = '%s.pub' % SSH_HOST_KEY
    deploy(proxmox_ssh, '%s/%s' % (TMP_DIR, priv), '%s/etc/ssh/%s'
           % (dst, priv), priv_key=True)
    deploy(proxmox_ssh, '%s/%s' % (TMP_DIR, pub), '%s/etc/ssh/%s'
           % (dst, pub), pub_key=True)
    deploy(proxmox_ssh, '%s/authorized_keys' % STATIC_DIR,
           '/root/.ssh/authorized_keys', priv_key=True)
    logger.info('Config deployed')
    logger.info('Unmounting of %s to %s by %s' % (src, dst, dev))
    check_exit(*image_umount(proxmox_ssh, dev, src, dst))
    logger.info('Image %s unmounted from %s by %s' % (src, dst, dev))
    logging.info('Closing connection to %s' % proxmox['host'])
    proxmox_ssh.close()
    logging.info('Connection to %s closed' % proxmox['host'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='raw-init')
    raw_init(configs, src, dst)
    sys.exit(0)
