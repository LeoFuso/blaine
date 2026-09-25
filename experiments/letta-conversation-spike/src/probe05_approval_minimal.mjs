// Probe 05: minimal approval mechanics in strict mode.
// Case builtin: unbound conversation, default toolset, model asked to Read a harmless file.
// Case external: bound conversation, model asked to create a Blaine summary Task.
// node src/probe05_approval_minimal.mjs STATE PORT AGENT_ID BINDINGS CASE DELAY_MS OUT
import { readFileSync, writeFileSync } from 'node:fs';
import { Human, brief } from './human.mjs';

const [state, port, agentId, bindingsPath, which, delay, out] = process.argv.slice(2);
const human = new Human({ state, port, name: `probe05-${which}`, approveDelayMs: Number(delay), approve: () => ({ behavior: 'allow' }) });
const start = await human.start({ agent_id: agentId, create_conversation: { body: {} }, mode: 'strict' });
if (which === 'external') {
  const bindings = JSON.parse(readFileSync(bindingsPath, 'utf8'));
  bindings.conversations[start.runtime.conversation_id] = { agent_id: agentId, project: 'spike-project' };
  writeFileSync(bindingsPath, JSON.stringify(bindings, null, 1));
  await new Promise((r) => setTimeout(r, 2500));
}
const text = which === 'builtin'
  ? 'Use the Read tool to read the file /etc/hostname and tell me its content.'
  : 'Create a Blaine summary Task for this text: "Synthetic spike text for approval mechanics."';
let turn;
try { turn = await human.say(text, { timeoutMs: 120000 }); } catch (error) { turn = { error: String(error) }; }
await new Promise((r) => setTimeout(r, 500));
const result = { case: which, delay_ms: Number(delay), runtime: start.runtime, stop_reason: turn.finished?.stop_reason ?? null, error: turn.error ?? null,
  approvals: human.approvals.map((a) => ({ tool: a.tool, request_id: a.request_id, ack: a.ack ?? null })),
  summary: turn.summary ?? null, transcript: brief(await human.transcript()) };
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result, null, 1).slice(0, 5000));
human.close();
process.exit(0);
