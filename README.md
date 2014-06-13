APC Network Power Management Controller
=======================================

Payton Quackenbush

Controls rebooting of APC network PDU switches with 'telnet' network interface.
Tested with the AP7900, but likely works with other models.

This handles locking of the device so that parallel calls will block, since
APC has a single telnet session.

Requirements
------------

- Python 2.x
- Python Expect (pexpect) library
- APC with telnet network interface (tested on AP7900)

Installation
------------

No source installation required.  Just download and run.

The APC needs to be set up with telnet enabled, and using a fixed IP address.
If a DHCP address is used, it may change, and you will have trouble connecting.

Usage
-----

# Power cycle (reboot) a single port
$ ./apc.py IPADDRESS --user USER --password PASSWORD --reboot PORT

# Example: reboot power port 1
$ ./apc.py 1.2.3.4 --user apc --password apc --reboot 1

# Display help
$ ./apc.py --help

Usage: apc.py [OPTIONS] APC-IP

Options:
  -h, --help           show this help message and exit
  --verbose            Verbose messages
  --quiet              Quiet
  --user=USER          Override the username
  --password=PASSWORD  Override the password
  --debug              Debug mode
  --reboot=REBOOT      Reboot an outlet
  --off=OFF            Turn off an outlet
  --on=ON              Turn on an outlet

Example session
---------------
$ ./apc.py 10.8.0.142 --reboot 8
Acquiring lock /tmp/apc.lock
Connecting to APC @ 10.8.0.142
Logged in as user apc, version 3.7.3
APC 10.8.0.142: Outlet #8 Rebooted
DISCONNECTED from 10.8.0.142
