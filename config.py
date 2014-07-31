import ConfigParser
from sys import stderr


class Config():

    """Contains all configuration variables"""
    items = {
        'logfile': '/var/log/opticsd/error.log',
        'log-level': 'Error',
        'pidfile': '/var/run/opticsd/opticsd.pid',
        'hostfile': 'etc/opticsd/hosts.txt',
        'max-threads': 4,
        'sleep-duration': 60,
        'threshold-interval': 50,
        'use-ssh': 1,
        'ssh-username': '',
        'ssh-password': '',
        'graphite-server': '',
        'graphite-port': '',
        'graphite-path': 'optics.\h.\i',
        'snmp-version': 2,
        'snmp-community': 'public',
        'snmp-retries': 5,
        'snmp-timeout': 1,
        }


def get(key):
    if key in Config.items:
        return Config.items[key]
    else:
        raise Exception('No such option: %s' % key)


def set_var(key, value):
    if key in Config.items:
        Config.items[key] = value
    else:
        raise Exception('No such option: %s' % key)


def load_config():
    parser = ConfigParser.RawConfigParser()
    parser.optionxform = str
    filenames = parser.read('/etc/opticsd/opticsd.conf')
    if len(filenames) == 0:
        print >> stderr, 'No config file found /etc/opticsd/opticsd.conf'
        exit(1)

    options = parser.items('Optics')
    options.extend(parser.items('Graphite'))
    options.extend(parser.items('snmp'))

    for i in options:
        if i[0] in Config.items:
            if i[1].isdigit():
                Config.items[i[0]] = int(i[1])
            else:
                Config.items[i[0]] = i[1]
        else:
            raise Exception('Unknow config option: %s' % i[0])
