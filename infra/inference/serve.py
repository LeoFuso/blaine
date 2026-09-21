#!/usr/bin/env python3
"""Launch one pinned local inference endpoint; never resolves mutable model refs."""
import json
import os
from pathlib import Path
import re
import sys


def command(config, kind):
    model = config[kind]
    if not re.fullmatch(r'[a-f0-9]{40}', model['revision']):
        raise ValueError('An immutable model revision is required')
    return [str(Path(config['env']) / 'bin/vllm'), 'serve', model['repository'],
            '--revision', model['revision'], '--tokenizer-revision', model['revision'],
            '--download-dir', config['cache'], *model['args']]


if __name__ == '__main__':
    config = json.loads(Path(sys.argv[1]).read_text())
    argv = command(config, sys.argv[2])
    os.environ['HF_HUB_CACHE'] = config['cache']
    cuda = str(Path(config['env']) / 'lib/python3.13/site-packages/nvidia/cu13')
    os.environ['CUDA_HOME'] = cuda
    os.environ['PATH'] = cuda + '/bin:' + str(Path(config['env']) / 'bin') + ':' + os.environ.get('PATH', '/usr/bin:/bin')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    # Cold CUDA compilation previously exhausted host RAM. Bound all builders,
    # including FlashInfer's ninja jobs and PyTorch's asynchronous compiler.
    os.environ.update(config['environment'])
    os.execv(argv[0], argv)
