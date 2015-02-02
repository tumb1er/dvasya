#!/usr/bin/env python3.3
# coding: utf-8

# $Id: $
import argparse
import os

ARGS = argparse.ArgumentParser(description="Run dvasya http server.")
ARGS.add_argument(
    '--host', action="store", dest='host',
    default='127.0.0.1', help='Host name')
ARGS.add_argument(
    '--port', action="store", dest='port',
    default=8080, type=int, help='Port number')
ARGS.add_argument(
    '--workers', action="store", dest='workers',
    default=2, type=int, help='Number of workers.')
ARGS.add_argument(
    '--heartbeat', action="store", dest="heartbeat",
    default=15, type=int, help='Seconds between heartbeat pings'
)
ARGS.add_argument(
    '--settings', action="store", dest="settings",
    default=None, type=str, help='DVASYA_SETTING_MODULE'
)
ARGS.add_argument(
    '--stderr', action="store_true", dest="stderr",
    default=False, help="don't close stderr and stdout while daemonizing"
)
ARGS.add_argument(
    '--no-daemon', action="store_true", dest="no_daemon",
    default=False, help="don't daemonize http server"
)
ARGS.add_argument(
    '--pid-file', action="store", dest="pidfile",
    default="dvasya.pid", type=str, help="path to pidfile"
)


def main():
    args = ARGS.parse_args()
    if ':' in args.host:
        args.host, port = args.host.split(':', 1)
        args.port = int(port)
    if args.settings:
        os.environ["DVASYA_SETTINGS_MODULE"] = args.settings
    from dvasya.server import Supervisor
    superviser = Supervisor(args)
    superviser.start()


if __name__ == '__main__':
    from dvasya import VERSION
    print("Running dvasya v%s" % VERSION)
    main()
