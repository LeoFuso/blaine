#!/usr/bin/env python3
"""Unix-socket HTTP tap in front of Blaine vLLM: records what Letta sends the model.

  llm_tap.py --unix STATE/sock/vllm.sock --upstream 127.0.0.1:8000 --out STATE/logs/llm-requests.jsonl

Per request it records the path, the offered tool names, tool_choice, stream flag,
message roles/sizes and, for tool messages, the tool_call ids. Tool schemas are
recorded once per distinct tool set. One upstream connection per request
(Connection: close), so HTTP framing stays trivial.
"""
import argparse
import asyncio
import hashlib
import json
import os
import time


async def read_request(reader):
    head = await reader.readuntil(b'\r\n\r\n')
    lines = head.decode('latin-1').split('\r\n')
    method, path, _ = lines[0].split(' ', 2)
    headers = {}
    for line in lines[1:]:
        if ':' in line:
            k, v = line.split(':', 1)
            headers[k.strip().lower()] = v.strip()
    body = b''
    if 'content-length' in headers:
        body = await reader.readexactly(int(headers['content-length']))
    elif headers.get('transfer-encoding', '').lower() == 'chunked':
        while True:
            size = int((await reader.readuntil(b'\r\n')).strip().split(b';')[0], 16)
            chunk = await reader.readexactly(size + 2)
            if size == 0:
                break
            body += chunk[:-2]
    return method, path, headers, body


def describe(body, seen):
    try:
        data = json.loads(body)
    except ValueError:
        return {'json': False}
    tools = data.get('tools') or []
    names = [t.get('function', {}).get('name', t.get('name')) for t in tools]
    key = hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest()[:16]
    info = {'model': data.get('model'), 'stream': data.get('stream'), 'tool_choice': data.get('tool_choice'),
            'tools': names, 'tools_digest': key, 'max_tokens': data.get('max_tokens') or data.get('max_completion_tokens')}
    messages = data.get('messages') or []
    info['messages'] = [{'role': m.get('role'), 'chars': len(json.dumps(m.get('content'))),
                         **({'tool_call_id': m['tool_call_id']} if m.get('tool_call_id') else {}),
                         **({'tool_calls': [c.get('function', {}).get('name') for c in m['tool_calls']]} if m.get('tool_calls') else {})}
                        for m in messages]
    if key not in seen and tools:
        seen.add(key)
        info['tool_schemas'] = tools
    if messages and messages[0].get('role') == 'system':
        info['system_digest'] = hashlib.sha256(json.dumps(messages[0].get('content')).encode()).hexdigest()[:16]
        info['system_chars'] = len(json.dumps(messages[0].get('content')))
    return info


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unix', required=True)
    parser.add_argument('--upstream', default='127.0.0.1:8000')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(args.unix)))
    name = os.path.basename(args.unix)
    if os.path.exists(name):
        os.unlink(name)
    host, port = args.upstream.rsplit(':', 1)
    seen = set()
    counter = [0]

    async def handle(reader, writer):
        try:
            while True:
                try:
                    method, path, headers, body = await read_request(reader)
                except (asyncio.IncompleteReadError, ConnectionError):
                    return
                counter[0] += 1
                record = {'ts': round(time.time(), 3), 'n': counter[0], 'method': method, 'path': path,
                          'body_bytes': len(body), **(describe(body, seen) if body else {})}
                up_reader, up_writer = await asyncio.open_connection(host, int(port))
                lines = [f'{method} {path} HTTP/1.1']
                for k, v in headers.items():
                    if k in ('connection', 'keep-alive', 'transfer-encoding', 'content-length'):
                        continue
                    lines.append(f'{k}: {v}')
                lines += [f'content-length: {len(body)}', 'connection: close', '', '']
                up_writer.write('\r\n'.join(lines).encode('latin-1') + body)
                await up_writer.drain()
                first = True
                size = 0
                while data := await up_reader.read(65536):
                    if first:
                        record['status'] = data.split(b' ', 2)[1].decode() if data.startswith(b'HTTP/') else '?'
                        first = False
                    size += len(data)
                    writer.write(data)
                    await writer.drain()
                up_writer.close()
                record['response_bytes'] = size
                record['done'] = round(time.time(), 3)
                with open(args.out, 'a') as out:
                    out.write(json.dumps(record) + '\n')
                # upstream said close; close the client side too
                writer.close()
                return
        except (ConnectionError, OSError):
            try:
                writer.close()
            except OSError:
                pass

    server = await asyncio.start_unix_server(handle, name)
    os.chmod(name, 0o600)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
