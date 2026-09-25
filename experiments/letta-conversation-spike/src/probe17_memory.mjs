// Probe 17: agent memory scope. A socket client writes one memory file; is it in the
// model context of two different conversations of the same agent (and not another agent)?
// node src/probe17_memory.mjs STATE PORT AGENT_ID BINDINGS OUT
import { readFileSync, writeFileSync } from 'node:fs';
import { createBoundConversation } from './setup.mjs';
import { V2Client, stateToken, sendAndWaitTurn, summarizeDeltas } from './v2client.mjs';

const [state, port, agentId, bindingsPath, out] = process.argv.slice(2);
const tap = () => readFileSync(`${state}/logs/llm-requests.jsonl`, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const c = new V2Client({ port: Number(port), token: stateToken(state), name: 'p17', trace: `${state}/logs/p17-trace.jsonl` });
await c.connect();
const fact = 'The synthetic spike project codename is BLUE-HERON-7.';
const w = await c.request({ type: 'write_memory_file', agent_id: agentId, path: 'system/spike-codename.md',
  content: `---\ndescription: Synthetic spike fact written by a socket client\n---\n${fact}\n`, commit_message: 'spike: socket-written memory' }, { timeoutMs: 60000 });
const convs = [];
for (let i = 0; i < 2; i++) convs.push(await createBoundConversation(c, agentId, bindingsPath, 'spike-project'));
const other = await c.request({ type: 'runtime_start', create_agent: { body: { name: 'memory-control', model: 'openai-compatible/nvidia/Qwen3.8-27B-NVFP4', system: 'Answer briefly.' }, pin_global: false },
  create_conversation: { body: {} }, mode: 'strict', wait_for_replay: true }, { timeoutMs: 60000 });
await c.request({ type: 'update_toolset', runtime: other.runtime, toolset_preference: 'none' });
const ask = 'What is the synthetic spike project codename? If you do not know, say UNKNOWN.';
const answers = [];
for (const runtime of [...convs, other.runtime]) {
  const n0 = tap().length;
  const t = await sendAndWaitTurn(c, runtime, ask, { timeoutMs: 300000 });
  const req = tap().slice(n0)[0];
  answers.push({ conversation: runtime.conversation_id, agent: runtime.agent_id, answer: summarizeDeltas(t.deltas).assistant.slice(0, 160), system_chars: req?.system_chars, system_digest: req?.system_digest });
  await new Promise((r) => setTimeout(r, 2000));
}
const result = { write_memory_file: { success: w.success, error: w.error ?? null }, fact, answers };
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result, null, 1));
c.close();
process.exit(0);
