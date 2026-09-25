#!/usr/bin/env python3
"""Byte-level TCP <-> Unix-socket bridge for the Letta network sandbox.

The sandbox has its own network namespace with only loopback. Unix sockets on a
shared bind mount are the only channels between it and the host:

  tcp-to-unix  --listen 127.0.0.1:PORT --unix PATH   accept TCP, connect to PATH
  unix-to-tcp  --unix PATH --connect 127.0.0.1:PORT  accept on PATH, connect TCP

Every accepted connection is logged as one JSON line on stderr (no payload).
"""
import argparse
import asyncio
import json
import os
import sys
import time


def log(**fields):
    print(json.dumps({'ts': round(time.time(), 3), **fields}), file=sys.stderr, flush=True)


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except OSError:
            pass


async def splice(client_reader, client_writer, open_upstream, label):
    try:
        up_reader, up_writer = await open_upstream()
    except OSError as error:
        log(event='upstream_unavailable', bridge=label, error=type(error).__name__)
        client_writer.close()
        return
    log(event='connection', bridge=label)
    await asyncio.gather(pipe(client_reader, up_writer), pipe(up_reader, client_writer))


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['tcp-to-unix', 'unix-to-tcp'])
    parser.add_argument('--listen')
    parser.add_argument('--connect')
    parser.add_argument('--unix', required=True)
    parser.add_argument('--label', default='bridge')
    args = parser.parse_args()
    # AF_UNIX paths are limited to 108 bytes; bind/connect relative to the socket dir.
    os.chdir(os.path.dirname(os.path.abspath(args.unix)))
    args.unix = os.path.basename(args.unix)
    if args.mode == 'tcp-to-unix':
        host, port = args.listen.rsplit(':', 1)
        if host != '127.0.0.1':
            raise SystemExit('loopback only')
        server = await asyncio.start_server(
            lambda r, w: splice(r, w, lambda: asyncio.open_unix_connection(args.unix), args.label),
            host, int(port))
    else:
        host, port = args.connect.rsplit(':', 1)
        if host != '127.0.0.1':
            raise SystemExit('loopback only')
        if os.path.exists(args.unix):
            os.unlink(args.unix)
        server = await asyncio.start_unix_server(
            lambda r, w: splice(r, w, lambda: asyncio.open_connection(host, int(port)), args.label),
            args.unix)
        os.chmod(args.unix, 0o600)
    log(event='listening', bridge=args.label, mode=args.mode)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
