"""Probe-only egress guard, also loaded by Python subprocesses via PYTHONPATH."""
import socket
import sys


def deny_network(event, args):
    if event == "socket.connect" and args[0].family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError("Graphify carveout: network connections prohibited during probe")


sys.addaudithook(deny_network)
