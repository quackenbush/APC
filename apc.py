#!/usr/bin/env python
'''
APC Network PDU Controller

Payton Quackenbush
Modified by Sebastien Celles

Tested with AP7900, but should work with similar models.
'''

import pexpect
import os
import re
import time

from argparse import ArgumentParser
from lockfile import FilesystemLock

APC_ESCAPE = '\033'

APC_IMMEDIATE_REBOOT = ['4', '3']
APC_IMMEDIATE_ON     = ['1', '1']
APC_IMMEDIATE_OFF    = ['3', '2']

APC_YES    = 'YES'
APC_LOGOUT = '4'

APC_VERSION_PATTERN = re.compile(' v(\d+\.\d+\.\d+)')

APC_DEFAULT_HOST     = os.environ.get('APC_HOST',     '192.168.1.2')
APC_DEFAULT_USER     = os.environ.get('APC_USER',     'apc')
APC_DEFAULT_PASSWORD = os.environ.get('APC_PASSWORD', 'apc')

LOCK_PATH = '/tmp/apc.lock'
LOCK_TIMEOUT = 60

class APC:
    def __init__(self, options):
        self.host = options.host
        self.user = options.user
        self.password = options.password
        self.verbose = options.verbose
        self.quiet = options.quiet
        self.connect()

    def info(self, msg):
        if not self.quiet:
            print(msg)

    def notify(self, outlet_name, state):
        print('APC %s: %s %s' % (self.host, outlet_name, state))

    def sendnl(self, a):
        self.child.send(a + '\r\n')
        if self.verbose:
            print(self.child.before)

    def _lock(self):
        self.info('Acquiring lock %s' % (LOCK_PATH))

        self.apc_lock = FilesystemLock(LOCK_PATH)

        count = 0
        while not self.apc_lock.lock():
            time.sleep(1)
            count += 1
            if count >= LOCK_TIMEOUT:
                raise SystemError('Cannot acquire %s\n' % (LOCK_PATH))

    def _unlock(self):
        self.apc_lock.unlock()

    def connect(self):
        self._lock()

        self.info('Connecting to APC @ %s' % self.host)
        self.child = pexpect.spawn('telnet %s' % self.host)

        self.child.timeout = 10
        self.child.setecho(True)

        self.child.expect('User Name : ')
        self.child.send(self.user + '\r\n')
        self.child.before
        self.child.expect('Password  : ')
        self.child.send(self.password + '\r\n')

        self.child.expect('Communication Established')

        header = self.child.before

        match = APC_VERSION_PATTERN.search(str(header))

        if not match:
            raise Exception('Could not parse APC version')

        self.version = match.group(1)
        self.is_new_version = (self.version[0] == '3')

        self.info('Logged in as user %s, version %s'
                  % (self.user, self.version))

    def get_outlet(self, outlet):
        if str(outlet) in ['*', '+', '9']:
            return (9, 'ALL outlets')
        else:
            # Assume integer outlet
            try:
                outlet = int(outlet)
                return (outlet, 'Outlet #%d' % outlet)

            except:
                raise SystemExit('Bad outlet: [%s]' % outlet)

    def configure_outlet(self, outlet):
        if self.is_new_version:
            self.sendnl('1')
            self.sendnl('2')
            self.sendnl('1')
            self.sendnl(str(outlet))

            self.sendnl('1')

        else:
            self.sendnl('1')
            self.sendnl('1')
            self.sendnl(str(outlet))

            self.sendnl('1')

        self.child.before

    def get_command_result(self):
        if self.is_new_version:
            self.child.expect('Command successfully issued')
        else:
            self.child.expect('Outlet State')

    def _escape_to_main(self):
        for i in range(6):
            self.child.send(APC_ESCAPE)

    def reboot(self, outlet):
        (outlet, outlet_name) = self.get_outlet(outlet)

        self.configure_outlet(outlet)

        self.sendnl(APC_IMMEDIATE_REBOOT[self.is_new_version])

        self.child.expect('Immediate Reboot')
        self.sendnl(APC_YES)
        self.sendnl('')

        self.get_command_result()

        self.notify(outlet_name, 'Rebooted')

        self._escape_to_main()

    def on_off(self, outlet, on):
        (outlet, outlet_name) = self.get_outlet(outlet)

        self.configure_outlet(outlet)

        if on:
            cmd = APC_IMMEDIATE_ON[self.is_new_version]
            str_cmd = 'On'
        else:
            cmd = APC_IMMEDIATE_OFF[self.is_new_version]
            str_cmd = 'Off'

        self.sendnl(cmd)
        self.sendnl(APC_YES)
        self.sendnl('')

        self.get_command_result()

        self.notify(outlet_name, str_cmd)

        self._escape_to_main()

    def on(self, outlet):
        self.on_off(outlet, True)

    def off(self, outlet):
        self.on_off(outlet, False)

    def debug(self):
        self.child.interact()

    def disconnect(self):
        # self._escape_to_main()

        self.sendnl(APC_LOGOUT)
        self.child.sendeof()
        if not self.quiet:
            print('DISCONNECTED from %s' % self.host)

        if self.verbose:
            print('[%s]' % ''.join(self.child.readlines()))

        self.child.close()
        self._unlock()


def main():
    parser = ArgumentParser(description='APC Python CLI')
    parser.add_argument('--host', action='store', default=APC_DEFAULT_HOST,
                        help='Override the host')
    parser.add_argument('--user', action='store', default=APC_DEFAULT_USER,
                        help='Override the username')
    parser.add_argument('--password', action='store', default=APC_DEFAULT_PASSWORD,
                        help='Override the password')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose messages')
    parser.add_argument('--quiet', action='store_true',
                        help='Quiet')
    parser.add_argument('--debug', action='store_true',
                        help='Debug mode')
    parser.add_argument('--reboot', action='store',
                        help='Reboot an outlet')
    parser.add_argument('--off', action='store',
                        help='Turn off an outlet')
    parser.add_argument('--on', action='store',
                        help='Turn on an outlet')

    args = parser.parse_args()

    is_command_specified = (args.reboot or args.debug or args.on or args.off)

    if not is_command_specified:
        parser.print_usage()
        raise SystemExit(1)

    try:
        apc = APC(args)
    except pexpect.TIMEOUT as e:
        raise SystemExit('ERROR: Timeout connecting to APC')

    if args.debug:
        apc.debug()
    else:
        try:
            if args.reboot:
                apc.reboot(args.reboot)
            elif args.on:
                apc.on(args.on)
            elif args.off:
                apc.off(args.off)
        except pexpect.TIMEOUT as e:
            raise SystemExit('APC failed!  Pexpect result:\n%s' % e)
        finally:
            apc.disconnect()


if __name__ == '__main__':
    main()
