"""Read an existing synthetic Task through the installed real ACP entrypoint."""
import asyncio,json
from pathlib import Path
from acp import Client,text_block
from acp.client import ClientSideConnection
from acp.stdio import spawn_stdio_transport

root=Path(__file__).resolve().parent
fixture=json.loads((root/'evidence/durable-fixture.json').read_text())
class Observer(Client):
 def __init__(self):self.chunks=[]
 async def session_update(self,session_id,update,**kwargs):
  if update.session_update=='agent_message_chunk':self.chunks.append(update.content.text)
async def main():
 observer=Observer()
 with (Path.home()/'.local/share/blaine/runtime/acp-acceptance.stderr').open('w') as err:
  async with spawn_stdio_transport(str(Path.home()/'.local/bin/blaine-agent'),stderr=err) as (reader,writer,process):
   conn=ClientSideConnection(observer,writer,reader)
   try:
    await conn.initialize(protocol_version=1)
    session=await conn.new_session(cwd=str(root.parents[1]),mcp_servers=[])
    result=await conn.prompt(session_id=session.session_id,prompt=[text_block('inspect '+fixture['tasks']['waiting'])])
    state=json.loads(''.join(observer.chunks))
    assert result.stop_reason=='end_turn'
    assert state==json.loads((root/'evidence/durable-waiting-before.json').read_text())
    (root/'evidence/acp-interaction.json').write_text(json.dumps({'status':'PASS','entrypoint':str(Path.home()/'.local/bin/blaine-agent'),'task_id':fixture['tasks']['waiting'],'lifecycle':state['lifecycle'],'state_matches':True},indent=2)+'\n')
    print('Installed actual ACP entrypoint inspected the same WAITING Task: PASS')
   finally:await conn.close()
asyncio.run(main())
