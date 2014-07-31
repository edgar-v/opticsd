
import netsnmp
import logging
import config
import subprocess
import math
from fabric.api import run, hide, settings

entity_sensor_oids = ['entSensorType',
                      'entSensorValue',
                      'entSensorPrecision',
                      'entSensorScale',
                      'entPhysicalName',
                      'entSensorThresholdValue']
dBm_data_type = '14'
watt_data_type = '6'
logger = None


class OpticalData():

    def __init__(self, physical_id=0, if_id=0):
        self.physical_id = physical_id
        self.if_id = if_id
        self.next_id = physical_id
        self.rx = None
        self.tx = None
        self.base = 0
        self.sensor_type = 0
        self.sensors = []
        self.warning_levels = []
        self.name = ''
        self.alias = ''

    def calculate(self):
        self.warning_levels = [int(x) * self.base for x in self.warning_levels]
        if self.sensor_type == watt_data_type:
            new_levels = []
            for i in range(len(self.warning_levels)):
                if self.warning_levels[i] <= 0:
                    continue
                newValue = 10 * math.log(self.warning_levels[i] * 1000, 10)
                newValue = '%.2f' % newValue
                new_levels.append(newValue)
            self.warning_levels = new_levels

    def csort(self):
        if self.warning_levels and len(self.warning_levels) == 8:
            order = [0, 6, 2, 4, 1, 7, 3, 5]
            self.warning_levels = [self.warning_levels[x] for x in order]


class Collect():
    """Collects data from different hosts"""
    def __init__(self, host, threshold_run):
        self.session = netsnmp.Session(
            DestHost=host,
            Version=config.get("snmp-version"),
            Community=config.get("snmp-community"),
            Retries=config.get("snmp-retries"),
            Timeout=config.get("snmp-timeout"))
        self.host = host
        global logger
        logger = logging.getLogger('log')
        self.threshold_run = threshold_run

    def collect(self):
        host_type = self.get_host_type()
        result = getattr(self, host_type + '_snmp')()
        if result:
            return result
        elif config.get("use-ssh") == 1:
            return getattr(self, host_type + '_ssh')()
        return None

    def get_host_type(self):
        try:
            cmd = 'dig HINFO %s | grep HINFO' % self.host
            output = subprocess.check_output(cmd, shell=True).lower()
        except Exception, e:
            logger.error(e)

        host_type = self.is_supported_host(output)
        if host_type:
            return host_type
        output = self.session.get(netsnmp.VarList(netsnmp.Varbind('sysDescr')))
        host_type = self.is_supported_host(output)
        if host_type:
            return host_type
        logger.warning('Could not determine host type for %s' % self.host)
        return None

    def is_supported_host(self, host):
        if 'cisco' in host or 'ios' in host:
            if 'xr' in host:
                return 'cisco_xr'
            elif 'xe' in host:
                return 'cisco_xe'
            return 'cisco'
        elif 'juniper' in host or 'junos' in host:
            return 'juniper'
        return None

    def juniper_snmp(self):
        return None

    def cisco_xe_snmp(self):
        # entAliasMappingIdentifier and entPhysicalChildIndex does not
        # cooperate well with IOS-XE
        return None

    def cisco_xe_ssh(self):
        # This seems to be a pain to do
        return None

    def juniper_ssh(self):
        optical_values = []
        try:
            cmd = ('show interfaces diagnostics optics | except current | ',
                   'except degree | except off | except voltage | except on ',
                   '| no more')
            opticinfo = [x.split()
                         for x in self.ssh(cmd).split('Physical interface:')
                         ]
            info = self.ssh("show interface descriptions | no-more | except down").split("\r\n")

            for ipinfo in info:
                ipinfo = ipinfo.split('up')
                if len(ipinfo) > 2:
                    ipinfo = [ipinfo[0].strip(), ipinfo[2].strip()]
                interface = ipinfo[0]
                for optinfo in opticinfo:
                    if optinfo and optinfo[0] == interface and len(optinfo) > 10:
                        values = []
                        while True:
                            i = optinfo.index('dBm')
                            values.append(optinfo[i-1].strip())
                            optinfo = optinfo[i+1:]
                            if 'dBm' not in optinfo:
                                break
                        opt = OpticalData()
                        opt.tx = values[0]
                        opt.rx = values[1]
                        opt.name = interface
                        opt.alias = ''.join(ipinfo[1:])
                        if self.threshold_run:
                            opt.warning_levels.extend(values[-8::])
                        optical_values.append(opt)

        except Exception, e:
            logger.error('juniper_ssh(): %s, %s' % (self.host, e))

        return optical_values

    def cisco_xr_ssh(self):
        return None

    def cisco_xr_snmp(self):
        return self.cisco_snmp()

    def cisco_snmp(self):
        # Holds a mapping between physical index and logical index
        mapping_vars = self.get_bulk('entAliasMappingIdentifier')
        if_status_vars = self.get_bulk('ifOperStatus')

        if_up = {x.iid for x in if_status_vars if x.val == '1'}
        opt_data = []

        for var in mapping_vars:
            if var.val is None:
                continue
            if_id = var.val.split('.')[-1]
            if if_id in if_up:
                opt_data.append(OpticalData(var.iid, if_id))

        self.get_sensor_values(opt_data)

        alias_vars = netsnmp.VarList()
        name_vars = netsnmp.VarList()

        for opt in opt_data:
            alias_vars.append(netsnmp.Varbind('ifAlias.%s' % opt.if_id))
            name_vars.append(netsnmp.Varbind('ifName.%s' % opt.if_id))

        for i in range(0, len(alias_vars), 10):
            self.session.get(alias_vars[i:i+10])
        for i in range(0, len(name_vars), 10):
            self.session.get(name_vars[i:i+10])

        for opt in opt_data:
            for name in name_vars:
                if opt.if_id == name.iid:
                    opt.name = name.val
                    break
            for alias in alias_vars:
                if opt.if_id == alias.iid:
                    opt.alias = alias.val
                    break

        return opt_data

    def get_sensor_values(self, opt_data):
        reverse_lookup = {}
        sensor_ids = []

        # Move down the tree
        for i in range(2):
            Vars = netsnmp.VarList()
            for opt in opt_data:
                Vars.append(netsnmp.Varbind('entPhysicalChildIndex.%s' % opt.next_id))
            self.session.getnext(Vars)

            for j, var in enumerate(Vars):
                reverse_lookup[var.val] = j
                opt_data[j].next_id = var.val

        # Get the physical id's for the sensors
        for i in range(0, len(opt_data), 10):
            Vars = netsnmp.VarList()
            for ids in opt_data[i:i+10]:
                Vars.append(netsnmp.Varbind('entPhysicalChildIndex.%s' % ids.next_id))
            self.session.getbulk(0, 5, Vars)
            for var in Vars:
                parent = var.iid.split('.')[0]
                if parent in reverse_lookup:
                    index = reverse_lookup[parent]
                    reverse_lookup[var.val] = index
                    sensor_ids.extend([oid + '.' + var.val for oid in entity_sensor_oids])

        sensor_vars = netsnmp.VarList()
        for sensor_id in sensor_ids:
            sensor_vars.append(netsnmp.Varbind(sensor_id))

        for i in range(0, len(sensor_vars), 40):
            self.session.get(sensor_vars[i:i+40])

        # This is defined in ENTITY-SENSOR-MIB from Cisco
        scale = {7: 0.000001, 8: 0.001, 9: 1, 10: 1000, 11: 1000000}

        threshold_ids = []

        # Calculate the dBm from the numbers we got
        for i in range(0, len(sensor_vars), len(entity_sensor_oids)):
            if sensor_vars[i].val == watt_data_type or sensor_vars[i].val == dBm_data_type:
                threshold_ids.append(sensor_vars[i].iid)
                base = 10 ** -int(sensor_vars[i+2].val) * scale[int(sensor_vars[i+3].val)]
                dBm = int(sensor_vars[i+1].val) * base

                if sensor_vars[i].val == watt_data_type:
                    if dBm <= 0:
                        continue
                    dBm = 10 * math.log(dBm * 1000, 10)

                index = reverse_lookup[sensor_vars[i].iid]
                opt_data[index].base = base
                opt_data[index].sensor_type = sensor_vars[i].val
                name_string = sensor_vars[i+4].val.lower()
                if 'rx' in name_string or 'receive' in name_string:
                    opt_data[index].rx = '%.2f' % dBm
                elif 'tx' in name_string or 'transmit' in name_string:
                    opt_data[index].tx = '%.2f' % dBm

        # Get threshold values

        if self.threshold_run:
            for i in range(0, len(threshold_ids), 8):
                Vars = netsnmp.VarList()
                for ids in threshold_ids[i:i+8]:
                    Vars.append(netsnmp.Varbind('entSensorThresholdValue.%s' % ids))
                self.session.getbulk(0, 4, Vars)
                for var in Vars:
                    if var.iid.split('.')[0] in reverse_lookup:
                        index = reverse_lookup[var.iid.split('.')[0]]
                        opt_data[index].warning_levels.append(var.val)
            for opt in opt_data:
                opt.calculate()
                opt.csort()

        return opt_data

    def cisco_ssh(self):
        optical_info = self.ssh('show interfaces transceiver | include [0-9]')
        if optical_info:
            optical_info = [x for x in optical_info.split('\r\n') if x != '']
            if len(optical_info) < 5:
                return None
        else:
            logger.error('Cisco ssh error. Got no optical info from %s' % self.host)
            return
        data = []
        interface_info = self.ssh('show interfaces description | exclude down')
        if interface_info:
            for interface in interface_info.split('\r\n')[1:]:
                interface = [x.strip()
                             for x in interface.split('up')
                             if x.strip() != '']
                if len(interface) == 2 and interface[1].find(',') != -1:
                    for opt in optical_info:
                        opt = [x.strip()
                               for x in opt.split(' ')
                               if x.strip() != '']
                        ifAlias = interface[1].split(',')[1].strip()
                        if interface[0] == opt[0] and '/' in opt[0]:
                            opt_data = OpticalData()
                            opt_data.rx = opt[3]
                            opt_data.tx = opt[4]
                            opt_data.name = interface[0]
                            opt_data.alias = ifAlias
                            data.append(opt_data)
                else:
                    error = ('Cisco ssh error. Could not parse ifDescr ',
                             '"%s" from host' % self.host)
                    logger.error(error)
        else:
            logger.error('Cisco ssh error. Got no interfaces from %s' % self.host)
            return

        return data

    def ssh(self, cmd):
        with settings(host_string=self.host, user=config.get('ssh-username'),
                      password=config.get('ssh-password').decode('base64'), warn_only=True,
                      abort_on_prompts=True, timeout=2):
            with hide('everything'):
                try:
                    return run(cmd, shell=False)
                except Exception, e:
                    logger.error(e)
                    return None

    def get_bulk(self, oid):
        
        start = 0
        data = []
        while True:
            Vars = netsnmp.VarList(netsnmp.Varbind(oid, start))
            self.session.getbulk(0, 100, Vars)

            for i in Vars:
                if i.tag != oid:
                    return data
                if i.val is None:
                    return data
                data.append(i)
            start_str = Vars[-1].iid
            if len(start_str.split('.')) == 2:
                start = int(start_str.split('.')[0])
            else:
                start = int(start_str)

