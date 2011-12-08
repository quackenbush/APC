#!/usr/bin/env python
'''
APC Network PDU Controller

Payton Quackenbush

Tested with AP7900, but should work with similar models.
'''

import pexpect
import sys
import re
import time

from optparse import OptionParser
from lockfile import FilesystemLock

APC_ESCAPE = "\033"

APC_IMMEDIATE_REBOOT = ["4", "3"]
APC_IMMEDIATE_ON     = ["1", "1"]
APC_IMMEDIATE_OFF    = ["3", "2"]

APC_YES = "YES"
APC_LOGOUT = "4"

APC_VERSION_PATTERN = re.compile(" v(\d+\.\d+\.\d+)")

APC_DEFAULT_USER = "apc"
APC_DEFAULT_PASSWORD = "apc"

LOCK_PATH = "/tmp/apc.lock"
LOCK_TIMEOUT = 60

class APC:
    def __init__(self, host, user = APC_DEFAULT_USER, password = APC_DEFAULT_PASSWORD, verbose = False, quiet = False):
        self.host = host
        self.user = user
        self.password = password
        self.verbose = verbose
        self.quiet = quiet
        self.connect()

    def info(self, msg):
        if not self.quiet:
            print msg

    def notify(self, outlet_name, state):
        print "APC %s: %s %s" % (self.host, outlet_name, state)

    def sendnl(self, a):
        self.child.send(a + "\r\n")
        if self.verbose:
            print self.child.before

    def _lock(self):
        self.info("Acquiring lock %s" % (LOCK_PATH))

        self.apc_lock = FilesystemLock(LOCK_PATH)

        count = 0
        while not self.apc_lock.lock():
            time.sleep(1)
            count += 1
            if count >= LOCK_TIMEOUT:
                raise SystemError("Cannot acquire %s\n" % (LOCK_PATH))

    def _unlock(self):
        self.apc_lock.unlock()

    def connect(self):
        self._lock()

        self.info("Connecting to APC @ %s" % self.host)
        self.child = pexpect.spawn('telnet %s' % self.host)

        self.child.timeout = 10
        self.child.setecho(True)

        self.child.expect("User Name : ")
        self.child.send(self.user + "\r\n")
        self.child.before
        self.child.expect("Password  : ")
        self.child.send(self.password + "\r\n")

        self.child.expect("Communication Established")

        header = self.child.before

        match = APC_VERSION_PATTERN.search(header)

        if not match:
            raise Exception, "Could not parse APC version"

        self.version = match.group(1)
        self.is_new_version = (self.version[0] == "3")

        self.info("Logged in as user %s, version %s" % (self.user, self.version))

    def get_outlet(self, outlet):
        if str(outlet) in ['*', '+', '9']:
            return (9, "ALL outlets")
        else:
            # Assume integer outlet
            try:
                outlet = int(outlet)
                return (outlet, "Outlet #%d" % outlet)

            except:
                raise SystemExit("Bad outlet: [%s]" % outlet)

    def configure_outlet(self, outlet):
        if self.is_new_version:
            self.sendnl("1")
            self.sendnl("2")
            self.sendnl("1")
            self.sendnl(str(outlet))

            self.sendnl("1")

        else:
            self.sendnl("1")
            self.sendnl("1")
            self.sendnl(str(outlet))

            self.sendnl("1")

        self.child.before

    def get_command_result(self):
        if self.is_new_version:
            self.child.expect("Command successfully issued")
        else:
            self.child.expect("Outlet State")

    def _escape_to_main(self):
        for i in range(6):
            self.child.send(APC_ESCAPE)

    def reboot(self, outlet):
        (outlet, outlet_name) = self.get_outlet(outlet)

        self.configure_outlet(outlet)

        self.sendnl(APC_IMMEDIATE_REBOOT[self.is_new_version])

        self.child.expect("Immediate Reboot")
        self.sendnl(APC_YES)
        self.sendnl("")

        self.get_command_result()

        self.notify(outlet_name, "Rebooted")

        self._escape_to_main()

    def on_off(self, outlet, on):
        (outlet, outlet_name) = self.get_outlet(outlet)

        self.configure_outlet(outlet)

        if on:
            cmd = APC_IMMEDIATE_ON[self.is_new_version]
            str_cmd = "On"
        else:
            cmd = APC_IMMEDIATE_OFF[self.is_new_version]
            str_cmd = "Off"

        self.sendnl(cmd)
        self.sendnl(APC_YES)
        self.sendnl("")

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
        #self._escape_to_main()

        self.sendnl(APC_LOGOUT)
        self.child.sendeof()
        if not self.quiet:
            print "DISCONNECTED from %s" % self.host

        if self.verbose:
            print '[%s]' % ''.join(self.child.readlines())

        self.child.close()
        self._unlock()

def parse_options():
    parser = OptionParser(usage = "%prog [OPTIONS] APC-IP")

    parser.add_option("--verbose", action = "store_true",
                      help = "Verbose messages")
    parser.add_option("--quiet", action = "store_true",
                      help = "Quiet")
    parser.add_option("--user", action = "store", type = "string", default = APC_DEFAULT_USER,
                      help = "Override the username")
    parser.add_option("--password", action = "store", type = "string", default = APC_DEFAULT_PASSWORD,
                      help = "Override the password")

    parser.add_option("--debug", action = "store_true",
                      help = "Debug mode")
    parser.add_option("--reboot", action = "store", type = "string",
                      help = "Reboot an outlet")
    parser.add_option("--off", action = "store", type = "string",
                      help = "Turn off an outlet")
    parser.add_option("--on", action = "store", type = "string",
                      help = "Turn on an outlet")

    options, rest = parser.parse_args()

    if len(rest) != 1:
        parser.print_usage()
        sys.exit(1)

    options.host = rest[0]

    return options

def main():
    options = parse_options()

    is_command_specified = (options.reboot or options.debug or options.on or options.off)

    if not is_command_specified:
        raise SystemExit("Must specify a command")

    apc = APC(options.host, options.user, options.password, verbose = options.verbose, quiet = options.quiet)

    if options.debug:
        apc.debug()
    else:
        try:
            if options.reboot:
                apc.reboot(options.reboot)
            elif options.on:
                apc.on(options.on)
            elif options.off:
                apc.off(options.off)
        except pexpect.TIMEOUT, e:
            raise SystemExit, "APC failed!  Pexpect result:\n%s" % e
        finally:
            apc.disconnect()

if __name__ == "__main__":
    main()
