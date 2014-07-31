#!/usr/bin/env python

import config
import socket
import Queue
import threading
from collect import Collect
import logging
from time import time
from sys import stderr
from daemon import runner
from time import sleep

hosts = []
sock = None


class Optics():

    def __init__(self):
        self.count = -1
        self.threshold_run = False
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path = config.get('pidfile')
        self.pidfile_timeout = 5
        self.work_queue = Queue.Queue()

    def run(self):
        while True:
            global sock
            sock = socket.socket()
            sock.connect((
                config.get("graphite-server"),
                config.get("graphite-port")
                ))
            if config.get("threshold-interval") != 0:
                self.count = (self.count + 1) % config.get("threshold-interval")
                self.threshold_run = True if self.count == 0 else False

            for host in hosts:
                self.work_queue.put(host)
            for i in range(min(config.get('max-threads'), len(hosts))):
                thread = threading.Thread(target=self.start_collect)
                thread.daemon = False
                thread.start()
            self.work_queue.join()
            sock.shutdown(socket.SHUT_WR)
            sock.close()
            sleep(config.get('sleep-duration'))

    def start_collect(self):
        while not self.work_queue.empty():
            host = self.work_queue.get()
            collector = Collect(host, self.threshold_run)
            data = collector.collect()
            if data:
                self.write(data, host)
            self.work_queue.task_done()

    def write(self, opt_data, host):
        """Writes data to the graphite server"""

        lines = []

        for opt in opt_data:
            path = config.get('graphite-path')
            if path.find('\d') != -1:
                opt.alias = opt.alias.split(',')
                if len(opt.alias) < 2:
                    warning = ('GraphitePath contains \'\\d\', but' + host +
                               ' ' + opt.name + ' have wrong description')
                    logger.warning(warning)

                    continue
                opt.alias = opt.alias[1].strip()
                path = path.replace('\d', opt.alias.replace('.', '-'))
            path = path.replace('\h', host)
            path = path.replace('\i', opt.name)
            values = [opt.rx, opt.tx] + opt.warning_levels
            names = ['tx', 'rx', 'txh2', 'txl2', 'txh1',
                     'txl1', 'rxh2', 'rxl2', 'rxh1', 'rxl1'
                     ]
            for i, val in enumerate(values):
                if val is not None:
                    lines.append('%s.%s %s %s' % (path, names[i], val, time()))
        data = '\n'.join(lines) + '\n'
        try:
            sock.sendall(data)
        except Exception, e:
            logger.error('sock.sendall() exception: %s' % e)

try:
    config.load_config()
except Exception, e:
    print >> stderr, e
    exit(1)

try:
    f = open(config.get("hostfile"))
    try:
        hosts = f.read().split("\n")
        if len(hosts) == 0:
            print >> stderr, 'hostfile empty'
            exit(1)
        if hosts[-1] == '':
            hosts = hosts[:-1]
    except IOError, e:
        print >> stderr, e
    finally:
        f.close()
        exit(1)
except IOError, e:
    print >> stderr, e
    exit(1)

optics = Optics()
logger = logging.getLogger('log')
logger.setLevel(config.get('log-level').upper())
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler = logging.FileHandler(config.get("logfile"))
handler.setFormatter(formatter)
logger.addHandler(handler)


daemon_runner = runner.DaemonRunner(optics)
daemon_runner.daemon_context.files_preserve = [handler.stream]
daemon_runner.do_action()
