// Crash test C: process death during compaction (scripted model, disposable state).
//   C0 control compaction; C1 SIGKILL during the summarization model call;
//   C2 injected SIGKILL at the compaction entry append (messages.jsonl);
//   C3 injected SIGKILL at the compaction's conversation.json rewrite.
// node src/probe11_compaction_crash.mjs STATE PORT CASE OUT
import { execFileSync } from 'node:child_process';
import { appendFileSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { V2Client, stateToken } from './v2client.mjs';

const [state, port, which, out] = process.argv.slice(2);
const HARNESS = new URL('../harness/', import.meta.url).pathname;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const lettactl = (env, ...args) => JSON.parse(execFileSync('python3', [`${HARNESS}lettactl.py`, ...args, state], { env: { ...process.env, ...env } }).toString().trim().split('\n').at(-1));
const integrity = (conv) => JSON.parse(execFileSync('python3', [`${HARNESS}integrity.py`, state, conv]).toString().trim().split('\n').at(-1));
const enqueue = (item) => appendFileSync(`${state}/work/hostile-queue.jsonl`, JSON.stringify(item) + '\n');
const convDir = (conv) => `${state}/home/.letta/lc-local-backend/conversations/${Buffer.from(`conversation:${conv}`).toString('base64url')}`;
async function connect(name) { for (let i = 0; i < 60; i++) { try { const c = new V2Client({ port: Number(port), token: stateToken(state), name, trace: `${state}/logs/${name}-trace.jsonl` }); await c.connect(3000); return c; } catch { await sleep(250); } } throw new Error('connect'); }
async function turn(c, runtime, text, cmid) {
  await c.request({ type: 'input', runtime, payload: { kind: 'create_message', messages: [{ role: 'user', content: text, client_message_id: cmid }] } }, { type: 'input_accepted' });
  const fin = await c.waitFor((f) => f.type === 'turn_finished' && f.runtime?.conversation_id === runtime.conversation_id, 120000, 'turn');
  await sleep(300);
  return fin.stop_reason;
}
const view = async (c, conv) => {
  const r = await c.request({ type: 'conversation_retrieve', conversation_id: conv }).catch((e) => ({ error: String(e) }));
  const m = await c.request({ type: 'conversation_messages_list', conversation_id: conv, query: { limit: 1000, order: 'asc' } }, { timeoutMs: 60000 }).catch((e) => ({ error: String(e) }));
  return { retrieve_ok: !!r.success, retrieve_error: r.error ?? null, in_context: r.conversation?.in_context_message_ids?.length ?? null,
    listed: m.messages?.length ?? null, list_error: m.error ?? (m.success === false ? m.error : null),
    summaries: (m.messages ?? []).filter((x) => /summary|compaction/i.test(x.message_type ?? '') || JSON.stringify(x).includes('"compaction"')).length };
};

const result = { case: which };
let c = await connect(`C-${which}-setup`);
const agentList = JSON.parse(readFileSync(`${state}/work/crash-state.json`, 'utf8'));
const agentId = agentList.setup.runtime.agent_id;
const start = await c.request({ type: 'runtime_start', agent_id: agentId, create_conversation: { body: {} }, mode: 'strict', wait_for_replay: true }, { timeoutMs: 60000 });
const runtime = start.runtime; const conv = runtime.conversation_id;
await c.request({ type: 'update_toolset', runtime, toolset_preference: 'none' });
for (let i = 0; i < 16; i++) await turn(c, runtime, `Compaction test ${which} message ${i}: the synthetic ledger balance is ${1000 + i}.`, `C-${which}-${i}`);
result.conversation = conv;
result.before = { integrity: integrity(conv), view: await view(c, conv) };
const compact = { type: 'conversation_compact', conversation_id: conv, body: { compaction_settings: { mode: 'all' } } };

if (which === 'C0') {
  enqueue({ text: 'SUMMARY C0: user reported synthetic ledger balances 1000..1015.' });
  const r = await c.request(compact, { timeoutMs: 120000 });
  result.compact_response = { success: r.success, error: r.error ?? null, result: r.compaction ?? r.result ?? null };
} else if (which === 'C1') {
  enqueue({ text: 'SUMMARY C1 (never delivered)', delay_ms: 15000 });
  c.send({ ...compact, request_id: 'c1' });
  await sleep(3000);
  result.kill = lettactl({}, 'kill', '--signal', 'KILL');
  c.kill();
  lettactl({}, 'start');
} else {
  const file = which === 'C2' ? 'messages.jsonl' : 'conversation.json';
  c.close();
  lettactl({}, 'kill', '--signal', 'TERM');
  lettactl({ SPIKE_STRACE: 'inject', SPIKE_INJECT_PATH: `${convDir(conv)}/${file}`, SPIKE_INJECT_WHEN: '1' }, 'start');
  c = await connect(`C-${which}-inject`);
  enqueue({ text: `SUMMARY ${which}: synthetic ledger balances 1000..1015.` });
  c.send({ ...compact, request_id: 'cinj' });
  await sleep(8000);
  const inj = readdirSync(`${state}/logs`).filter((f) => f.startsWith('inject-')).sort().at(-1);
  result.inject_trace = readFileSync(`${state}/logs/${inj}`, 'utf8').trim().split('\n').filter((l) => /write|openat|killed/.test(l)).slice(-4).map((l) => l.slice(0, 160));
  c.kill();
  const pid = JSON.parse(readFileSync(`${state}/control.json`, 'utf8')).generations.at(-1).server_pid;
  let alive = true; try { process.kill(pid, 0); } catch { alive = false; }
  result.server_killed_by_injection = !alive;
  if (alive) lettactl({}, 'kill', '--signal', 'KILL');
  result.after_kill_integrity = integrity(conv);
  lettactl({}, 'start');
}
c.close();
c = await connect(`C-${which}-after`);
result.after = { integrity: integrity(conv), view: await view(c, conv) };
const resumed = await c.request({ type: 'runtime_start', agent_id: agentId, conversation_id: conv, mode: 'strict', wait_for_replay: true }, { timeoutMs: 60000 }).catch((e) => ({ error: String(e) }));
result.after.runtime_start = { success: resumed.success ?? false, error: resumed.error ?? null };
if (resumed.success) result.after.turn = await turn(c, runtime, `After ${which}: what was the balance in message 3?`, `C-${which}-after`).catch((e) => String(e));
const last = readFileSync(`${state}/work/hostile-requests.jsonl`, 'utf8').trim().split('\n').slice(-1).map((l) => JSON.parse(l))[0];
result.after.last_model_request_roles = last?.roles;
c.close();
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
const pick = (i) => i && { bytes: i.bytes, messages: i.messages, types: i.entry_types, unparseable: i.unparseable_lines?.length, cj: i.conversation_json, in_ctx: i.in_context, missing: i.in_context_missing_from_transcript?.length, summaries: i.compaction_summaries };
console.log(JSON.stringify({ case: which, before: pick(result.before.integrity), compact_response: result.compact_response, inject_trace: result.inject_trace, killed: result.server_killed_by_injection ?? result.kill?.namespace_gone,
  after_kill: pick(result.after_kill_integrity), after: pick(result.after.integrity), view_after: result.after.view, runtime_start: result.after.runtime_start, turn: result.after.turn, roles: result.after.last_model_request_roles?.join(' ') }, null, 1));
process.exit(0);
