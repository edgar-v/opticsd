opticsd
=====

opticsd is a python daemon that can collect optical data such as rx/tx output power from Cisco IOS/IOS-XE/IOS-XR and Juniper Junos. The main method for collecting the data is through SNMP, however it can be configured to fall back to ssh should SNMP fail.

# Usage

Install git, libsnmp-base, snmp-mibs-downloader, python-netsnmp
- apt-get install git libsnmp-base snmp-mibs-downloader python-netsnmp

The daemon can then be started with:
- python opticsd.py start

And stopped with
- python opticsd.py stop

...

# opticsd.conf

logfile = /var/log/opticsd/error.log
- Location of the log file, ensure the user has write permission

log-level = warning
- The amount of logging. The availiable levels are (from least to most log): critical, error, warning, info, debug

pidfile = /var/run/opticsd/opticsd.pid
- Location of the file to indicate that the daemon is running

hostfile = /etc/opticsd/hosts.txt
- Location of the hosts file. The hosts that the daemon will gather data from. One host per line

max-threads = 4
- How many threads should the daemon be allowed to use

sleep-duration = 60
- The time (in seconds) that the daemon should sleep between each run

threshold-interval = 50
- How often should the daemon gather threshold values. 0 means never, 1 means every time, 2 means every second time and so on

use-ssh = 1
- Specifies if ssh should be used if snmp does not get a response. 1 for on, 0 for off

ssh-username = yourusername
- The username to use when ssh-ing

ssh-password = yourpassword
- The password to use when ssh-ing (base64 encoded)

graphite-server = 158.38.100.12
- The ip or hostname of the graphite server you want to send data to

graphite-port = 2003
- The tcp port number of the graphite server you want to send data to

graphite-path = optics.testing.\d
- The graphite path that the data will have
 - \h will be replaced with the hostname. For example: uninett-gw.uninett.no
 - \i is the physical interface name. For example: Te1/6
 - \d is the second comma-separated value in the interface's description. For example: "first value, second value, third value" would become "second value"

snmp-version = 2
- The version of snmp that should be used

snmp-community = public
- The community that your hosts have

snmp-retries = 5
- The number of retries that snmp will do

snmp-timeout = 1
- the time (in seconds) to wait for a response


# opticsd.py


The daemon will first attempt to find the host type by using dig HINFO and snmp.

If the host type is recognized, it will then attempt to speak SNMP with it and collect the data.

If this fails (for whatever the reason), the daemon will try to collect the data with SSH (if configured for it)

The supported OSes are Juniper's JunOS, Cisco's IOS, IOS-XE, and IOS-XR
