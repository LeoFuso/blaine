#!/usr/bin/env python3
"""Fetch only the pinned model artifacts; run during provisioning, never at boot."""
import json
from pathlib import Path
import sys
from huggingface_hub import snapshot_download

c=json.loads(Path(sys.argv[1]).read_text())
for kind in ['generation','embedding']:
    model=c[kind]
    snapshot_download(model['repository'], revision=model['revision'], cache_dir=c['cache'],
        allow_patterns=['*.safetensors','*.safetensors.index.json','pytorch_model.bin',
            'config.json','generation_config.json','tokenizer*','special_tokens_map.json',
            '*.model','chat_template*','preprocessor_config.json','processor_config.json',
            'sentence_bert_config.json','config_sentence_transformers.json','modules.json','1_Pooling/config.json'])
