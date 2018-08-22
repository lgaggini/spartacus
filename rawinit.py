#! /usr/bin/env python

from paramiko import SSHClient, WarningPolicy
from paramiko import RSAKey, ECDSAKey
from jinja2 import Environment, FileSystemLoader
from yamlschema import YamlSchema
import sys
import logging
import argparse
import coloredlogs
import subprocess
import os
import importlib
from pysshops import SshOps, SftpOps, SshCommandBlockingException


SETTINGS_KEY = ['PROXMOX', 'SSH_HOST_KEY', 'DEV', 'TMP_DIR', 'STATIC_DIR',
                'VM_RESOURCES', 'VM_DEFAULTS', 'VM_DEFAULTS8', 'KVM_THRES',
                'IMAGES_BASEPATH', 'TEMPLATE_MAP', 'WORKING_MNT']
LOG_LEVELS = ['debug', 'info', 'warning', 'error', 'critical']

logger = logging.getLogger('rawinit')


def log_init(loglevel):
    """ initialize the logging system """
    FORMAT = '%(asctime)s %(levelname)s %(module)s %(message)s'
    logging.basicConfig(format=FORMAT, level=getattr(logging,
                                                     loglevel.upper()))
    coloredlogs.install(level=loglevel.upper())


def settings_load(settings_file):
    """ load settings from settings package """
    logger.info('loading settings from %s' % (settings_file))
    try:
        settings_basename = os.path.basename(settings_file)
        module_name = 'settings.%s' % (os.path.splitext(settings_basename)[0])
        logger.debug(module_name)
        settings_module = importlib.import_module(module_name)
    except ImportError:
        logger.error('no such file: %s' % (settings_file))
        sys.exit('exiting')
    settings = {}
    try:
        for setting in SETTINGS_KEY:
            settings[setting] = getattr(settings_module, setting)
    except AttributeError as ex:
        logger.error('settings loading error: %s' % (ex))
        sys.exit('exiting')
    return settings


def template_compile(configs):
    """ compile jinja template """
    env = Environment(loader=FileSystemLoader('templates'))

    custom_tmp_fd = '%s/%s' % (cfg['TMP_DIR'], configs['name'])
    try:
        subprocess.call(['mkdir', '-p', custom_tmp_fd])
    except subprocess.CalledProcessError as ex:
        logger.error('error creating the folder %s: %s' % (custom_tmp_fd,
                                                           ex.output))
        sys.exit('exiting')

    for config_key in cfg['TEMPLATE_MAP'].keys():
        j2_template = env.get_template('%s.j2' % config_key)
        with open('%s/%s' % (custom_tmp_fd, config_key), 'w') as config_file:
            if cfg['TEMPLATE_MAP'][config_key] in configs:
                var = configs[cfg['TEMPLATE_MAP'][config_key]]
                config_file.write(j2_template.render(var=var))


def nbd_module(ssh):
    """ load the nbd kernel module """
    logger.info('modprobe of nbd module')
    command = 'sudo modprobe nbd'
    ssh.remote_command(command)


def image_mount(ssh, dev, src, dst, part):
    """ create a custom mountpoint and mount a qemu
    supported image by nbd """
    command = 'sudo qemu-nbd -f raw -c %s %s' % (dev, src)
    ssh.remote_command(command)
    command = 'mkdir -p %s' % dst
    ssh.remote_command(command)
    src_nbd = '%sp%s' % (dev, part)
    command = 'sudo mount %s %s' % (src_nbd, dst)
    ssh.remote_command(command)


def image_umount(ssh, dev, src, dst):
    """ umount a qemu mounted image by nbd
    and remove custom mountpoint """
    double_check_path(dst, cfg['WORKING_MNT'])
    command = 'sudo umount %s' % dst
    ssh.remote_command(command)
    command = 'rmdir %s' % dst
    ssh.remote_command(command)
    command = 'sudo qemu-nbd -d %s' % (dev)
    ssh.remote_command(command)


def check_mount(ssh, dev, src, dst):
    """ check if the target mount is mounted """
    command = 'mount | grep -q %s' % dst
    try:
        ssh.remote_command(command)
    except SshCommandBlockingException:
        return False
    return True


def ssh_folder_init(ssh, dst):
    """ create and set permission for the user .ssh folder """
    command = 'mkdir -p %s/root/.ssh && chmod 0700 %s/root/.ssh' % (dst,
                                                                    dst)
    ssh.remote_command(command)


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
    hostname = ssh.remote_command(command)
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


def rawinit(settings, configs, src, dst, dev='/dev/nbd0', part='1',
            readonly=False, log_level='info'):
    # log init
    log_init(log_level)

    # load settings
    global cfg
    cfg = settings
    logger.debug(cfg)

    # compile template
    template_compile(configs)

    # exit if it's a readonly run
    if readonly:
        logger.info('running in readonly mode, templates compiled')
        sys.exit('exiting')

    # proxmox ssh connection
    proxmox_srv = SshOps(cfg['PROXMOX']['SSH_HOST'],
                         cfg['PROXMOX']['USER'].split('@')[0])

    with proxmox_srv as proxmox_ssh:

        # load nbd moudule on remote host
        logger.info('modprobing of nbd module')
        nbd_module(proxmox_ssh)
        logger.info("nbd module modprobed")

        # mount vm image
        if check_mount(proxmox_ssh, dev, src, dst):
            logger.info('mountpoint %s busy, unmounting it' % dst)
            image_umount(proxmox_ssh, dev, src, dst)
        logger.info('mounting %s to %s by %s' % (src, dst, dev))
        image_mount(proxmox_ssh, dev, src, dst, part)
        logger.info('image %s mounted to %s by %sp%s' % (src, dst, dev, part))

        # double check hostname on the mounted vm
        if (not double_check_hostname(proxmox_ssh, dst, configs['template'])):
            image_umount(proxmox_ssh, dev, src, dst)
            sys.exit('exiting')

        # deploy configurations
        logger.info('deploy configurations')
        custom_tmp_fd = '%s/%s' % (cfg['TMP_DIR'], configs['name'])

        proxmox_sftp_srv = SftpOps(cfg['PROXMOX']['SSH_HOST'],
                                   cfg['PROXMOX']['USER'].split('@')[0])
        with proxmox_sftp_srv as proxmox_sftp:
            logger.debug(proxmox_sftp)
            logger.info('interfaces')
            proxmox_sftp.deploy('%s/interfaces' % custom_tmp_fd,
                                '%s/etc/network/interfaces' % dst)
            logger.info('hostname')
            proxmox_sftp.deploy('%s/hostname' % custom_tmp_fd,
                                '%s/etc/hostname' % dst)
            logger.info('serverfarm')
            proxmox_sftp.deploy('%s/serverfarm' % custom_tmp_fd,
                                '%s/etc/serverfarm' % dst)
            logger.info('interfaces')
            proxmox_sftp.deploy('%s/pu_puppetenvironment' % custom_tmp_fd,
                                '%s/etc/pu_puppetenvironment' % dst)
            logger.info('hosts')
            proxmox_sftp.deploy('%s/hosts' % custom_tmp_fd,
                                '%s/etc/hosts' % dst)
            logger.info('puppet')
            proxmox_sftp.deploy('%s/puppet.conf' % custom_tmp_fd,
                                '%s/etc/puppet/puppet.conf' % dst)
            # generate ssh host keys
            logger.info('generate and deploy tmp RSA 2048 bit host keys')
            generate_ssh_hostkeys('%s/%s' % (custom_tmp_fd,
                                             cfg['SSH_HOST_KEY']))
            logger.info('generated tmp RSA 2048 bit host keys for first ssh access')
            priv = '%s' % cfg['SSH_HOST_KEY']
            pub = '%s.pub' % cfg['SSH_HOST_KEY']
            proxmox_sftp.deploy('%s/%s' % (custom_tmp_fd, priv),
                                '%s/etc/ssh/%s' % (dst, priv))
            proxmox_sftp.chmod('%s/etc/ssh/%s' % (dst, priv), 0600)
            proxmox_sftp.deploy('%s/%s' % (custom_tmp_fd, pub), '%s/etc/ssh/%s'
                                % (dst, pub))
            proxmox_sftp.chmod('%s/etc/ssh/%s' % (dst, pub), 0644)
            # public key to ssh access as root user
            logger.info('creating the root .ssh folder')
            ssh_folder_init(proxmox_ssh, dst)
            proxmox_sftp.deploy('%s/authorized_keys' % cfg['STATIC_DIR'],
                                '%s/root/.ssh/authorized_keys' % dst)
            proxmox_sftp.chmod('%s/root/.ssh/authorized_keys' % dst, 0600)
            logger.info('config deployed')

        # deploy end, umount vm disk and close ssh connection
        logger.info('unmounting of %s to %s by %s' % (src, dst, dev))
        image_umount(proxmox_ssh, dev, src, dst)
        logger.info('image %s unmounted from %s by %s' % (src, dst, dev))
        logger.info('closing connection to %s' % cfg['PROXMOX']['SSH_HOST'])
    logger.info('connection to %s closed' % cfg['PROXMOX']['SSH_HOST'])


if __name__ == '__main__':

    description = 'rawinit, customize a debian kvm disk image'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--settings', default='settings',
                        help='custom settings file in settings package')
    parser.add_argument('-s', '--source', required=True,
                        help='the source id image to customize')
    parser.add_argument('-t', '--target', required=True,
                        help='the mount point to use for customization')
    parser.add_argument('-i', '--inventory', default=None,
                        help='Yaml file path to read', required=True)
    parser.add_argument('-r', '--readonly', dest='readonly',
                        action='store_true',
                        help='readonly mode for debug (default disabled)')
    parser.set_defaults(readonly=False)
    parser.add_argument('-l', '--log-level', default=LOG_LEVELS[1],
                        help='log level (default info)', choices=LOG_LEVELS)

    # parse cli options
    options = {}
    cli_options = parser.parse_args()
    log_init(cli_options.log_level)
    logger.debug(cli_options)

    # load settings from setting package
    global cfg
    cfg = settings_load(cli_options.settings)
    logger.debug(cfg)

    # load desired config from yaml
    yaml_schema = YamlSchema(cfg['VM_DEFAULTS'], cfg['VM_RESOURCES'])
    parsed_options = yaml_schema.parse(cli_options.inventory)
    logger.debug(parsed_options)
    logger.debug(parsed_options['template'])
    options = parsed_options
    # fix puppet
    options['puppet'] = {}
    options['puppet']['puppetmaster'] = options['puppetmaster']
    options['puppet']['env'] = options['env']
    # fix readonly
    options['readonly'] = cli_options.readonly
    readonly = options['readonly']
    logger.debug(options)

    # call to raw init
    rawinit(cfg, options, cli_options.source, cli_options.target,
            readonly=readonly, log_level=cli_options.log_level)

    sys.exit(0)
