// Probe 10: deterministic process death inside the conversation.json rewrite window
// (strace injects SIGKILL at the first write() after its O_TRUNC open), then recovery.
// node src/probe10_inject_crash.mjs STATE PORT AGENT_ID CONVERSATION_ID OUT
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { V2Client, stateToken } from './v2client.mjs';

const [state, port, agentId, conv, out] = process.argv.slice(2);
const HARNESS = new URL('../harness/', import.meta.url).pathname;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const dir = `${state}/home/.letta/lc-local-backend/conversations/${Buffer.from(`conversation:${conv}`).toString('base64url')}`;
const snapshot = () => Object.fromEntries(readdirSync(dir).map((f) => { const b = readFileSync(`${dir}/${f}`); return [f, { bytes: b.length, sha256: createHash('sha256').update(b).digest('hex').slice(0, 16) }]; }));
const lettactl = (env, ...args) => JSON.parse(execFileSync('python3', [`${HARNESS}lettactl.py`, ...args, state], { env: { ...process.env, ...env } }).toString().trim().split('\n').at(-1));
const integrity = () => JSON.parse(execFileSync('python3', [`${HARNESS}integrity.py`, state, conv]).toString().trim());
async function connect(name) { for (let i = 0; i < 40; i++) { try { const c = new V2Client({ port: Number(port), token: stateToken(state), name, trace: `${state}/logs/${name}-trace.jsonl` }); await c.connect(3000); return c; } catch { await sleep(250); } } throw new Error('connect'); }

const result = { conversation: conv, file: `${dir}/conversation.json` };
result.before = snapshot();
lettactl({}, 'kill', '--signal', 'TERM');
result.inject_start = lettactl({ SPIKE_STRACE: 'inject', SPIKE_INJECT_PATH: `${dir}/conversation.json`, SPIKE_INJECT_WHEN: '1' }, 'start');
let client = await connect('inject-1');
await client.request({ type: 'runtime_start', agent_id: agentId, conversation_id: conv, mode: 'strict', wait_for_replay: true }, { timeoutMs: 60000 });
client.send({ type: 'input', runtime: { agent_id: agentId, conversation_id: conv }, request_id: 'inj', payload: { kind: 'create_message', messages: [{ role: 'user', content: 'message that triggers the conversation.json rewrite', client_message_id: 'inject-probe-1' }] } });
await sleep(3000);
const pid = JSON.parse(readFileSync(`${state}/control.json`, 'utf8')).generations.at(-1).server_pid;
let alive = true; try { process.kill(pid, 0); } catch { alive = false; }
result.server_alive_after_injection = alive;
result.after_kill = snapshot();
result.strace_tail = readFileSync(`${state}/logs/${readdirSync(`${state}/logs`).filter((f) => f.startsWith('inject-')).sort().at(-1)}`, 'utf8').trim().split('\n').slice(-6);
client.kill();
if (alive) lettactl({}, 'kill', '--signal', 'KILL');
result.integrity_after_kill = integrity();
// Recovery: plain restart, then look for the conversation.
result.restart = lettactl({}, 'start');
client = await connect('inject-2');
const listed = await client.request({ type: 'conversation_list', agent_id: agentId, query: { limit: 50 } }).catch((e) => ({ error: String(e) }));
result.conversation_list = listed.error ? listed : { success: listed.success, ids: (listed.conversations ?? listed.items ?? []).map((c) => c.id) };
const retrieved = await client.request({ type: 'conversation_retrieve', conversation_id: conv }).catch((e) => ({ error: String(e) }));
result.conversation_retrieve = { success: retrieved.success, error: retrieved.error ?? null, in_context: retrieved.conversation?.in_context_message_ids?.length ?? null };
const started = await client.request({ type: 'runtime_start', agent_id: agentId, conversation_id: conv, mode: 'strict', wait_for_replay: true }, { timeoutMs: 60000 }).catch((e) => ({ error: String(e) }));
result.runtime_start = { success: started.success, error: started.error ?? null };
const msgs = await client.request({ type: 'conversation_messages_list', conversation_id: conv, query: { limit: 1000, order: 'asc' } }, { timeoutMs: 60000 }).catch((e) => ({ error: String(e) }));
result.messages_readable = { success: msgs.success, count: msgs.messages?.length ?? null, error: msgs.error ?? null, probe_present: (msgs.messages ?? []).filter((m) => m.otid === 'inject-probe-1').length };
if (started.success) {
  const acc = await client.request({ type: 'input', runtime: { agent_id: agentId, conversation_id: conv }, payload: { kind: 'create_message', messages: [{ role: 'user', content: 'post-recovery message', client_message_id: 'inject-post-1' }] } }, { type: 'input_accepted' });
  const fin = await client.waitFor((f) => f.type === 'turn_finished' && f.runtime?.conversation_id === conv, 120000, 'turn').catch((e) => ({ error: String(e) }));
  result.post_recovery_turn = { accepted: acc.accepted, stop: fin.stop_reason ?? fin.error };
}
result.after_recovery = snapshot();
result.integrity_after_recovery = integrity();
client.close();
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result, null, 1).slice(0, 6000));
process.exit(0);
