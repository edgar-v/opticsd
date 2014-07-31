import ConfigParser


class Config():

    """Contains all configuration variables"""
    items = {
        'LogFile': 'error.log',
        'Loglevel': 'Error',
        'Hostfile': 'hosts.txt',
        'PidFile': '/var/run/opticsd.pid',
        'User': '',
        'Password': '',
        'GraphiteServer': '',
        'GraphitePort': '',
        'GraphitePath': 'optics.\h.\i',
        'SleepDuration': 300,
        'ThresholdInterval': 50,
        'Version': 2,
        'Community': 'public',
        'Retries': 3,
        'Timeout': 500000,
        'MaxThreads': 4,
        'ThresholdRun': False
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
    parser.read('optics.conf')

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
