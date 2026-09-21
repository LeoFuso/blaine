#!/usr/bin/env python3
"""Update existing MIRIX model binding through its manager; preserve identities."""
import asyncio
import json
import os
from pathlib import Path
import runpy
import sys

os.umask(0o077)
runpy.run_path(str(Path(__file__).with_name('mirix-launch.py')))['configure']()
sys.path.insert(0,str(Path.home()/'workspace/mirix'))
from mirix.services.agent_manager import AgentManager
from mirix.services.client_manager import ClientManager

async def main():
    before=json.loads(Path(sys.argv[1]).read_text())
    manager=AgentManager()
    client=await ClientManager().get_client_by_id('client-df3da0d9')
    rollback=Path.home()/'.local/share/blaine/service-adoption-rollback/mirix-models'
    rollback.mkdir(parents=True,exist_ok=True,mode=0o700)
    changed=[]
    for observed in before['agents']:
        agent=await manager.get_agent_by_id(observed['id'],client)
        config=agent.llm_config
        assert config.model_endpoint=='http://127.0.0.1:8000/v1'
        assert config.model in ['Qwen/Qwen3.5-9B','nvidia/Qwen3.8-27B-NVFP4']
        saved=rollback/(agent.id+'.json')
        if not saved.exists(): saved.write_text(config.model_dump_json())
        updated=config.model_copy(update={'model':'nvidia/Qwen3.8-27B-NVFP4','context_window':131072})
        await manager.update_llm_config(agent.id,updated,client)
        changed.append(agent.id)
    print('Updated existing MIRIX local generation bindings:',len(changed),'; identities and embedding configs retained')

asyncio.run(main())
