// Probe 03: persisted toolset "none" + registered blaine_* tools; a turn sent
// WITHOUT any client_tool_allowlist must offer only blaine_* tools (tap-verified).
// node src/probe03_toolset_none.mjs STATE PORT AGENT_ID BINDINGS OUT
import { readFileSync, writeFileSync } from 'node:fs';
import { Human } from './human.mjs';

const [state, port, agentId, bindingsPath, out] = process.argv.slice(2);
const tap = () => readFileSync(`${state}/logs/llm-requests.jsonl`, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const human = new Human({ state, port, name: 'probe03' });
const start = await human.start({ agent_id: agentId, create_conversation: { body: {} }, mode: 'strict' });
const runtime = start.runtime;
const toolset = await human.client.request({ type: 'update_toolset', runtime, toolset_preference: 'none' });
// bind the conversation so the controller registers blaine_* tools for it
const bindings = JSON.parse(readFileSync(bindingsPath, 'utf8'));
bindings.conversations[runtime.conversation_id] = { agent_id: agentId, project: 'spike-project' };
writeFileSync(bindingsPath, JSON.stringify(bindings, null, 1));
await new Promise((r) => setTimeout(r, 2500));
const before = tap().length;
const turn = await human.say('Which tools can you call? Names only, comma separated. Do not call any.');
const requests = tap().slice(before);
const result = { runtime, update_toolset: { success: toolset.success, current: toolset.current_toolset, preference: toolset.current_toolset_preference },
  assistant: turn.summary.assistant, offered_tools: requests.map((r) => r.tools) };
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result, null, 1));
human.close();
process.exit(0);
