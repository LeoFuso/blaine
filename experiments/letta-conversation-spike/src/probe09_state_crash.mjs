// Crash tests A (append) and the transcript-rewrite window, against disposable state.
// node src/probe09_state_crash.mjs STATE PORT OUT [grow_turns] [grow_bytes] [append_kills] [rewrite_kills]
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { V2Client, stateToken } from './v2client.mjs';

const [state, port, out, growTurns = '60', growBytes = '120000', appendKills = '30', rewriteKills = '30'] = process.argv.slice(2);
const HARNESS = new URL('../harness/', import.meta.url).pathname;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const lettactl = (...args) => JSON.parse(execFileSync('python3', [`${HARNESS}lettactl.py`, ...args, state]).toString().trim().split('\n').at(-1));
const integrity = (conv) => JSON.parse(execFileSync('python3', [`${HARNESS}integrity.py`, state, conv]).toString().trim().split('\n').at(-1) || 'null');
const MODEL = 'llama.cpp/scripted';

async function connect(name) {
  for (let i = 0; i < 40; i++) {
    try { const c = new V2Client({ port: Number(port), token: stateToken(state), name, trace: null }); await c.connect(3000); return c; } catch { await sleep(250); }
  }
  throw new Error('cannot connect');
}

async function turn(client, runtime, text, cmid) {
  const acc = await client.request({ type: 'input', runtime, payload: { kind: 'create_message', messages: [{ role: 'user', content: text, client_message_id: cmid }] } }, { type: 'input_accepted' });
  const fin = await client.waitFor((f) => f.type === 'turn_finished' && f.runtime?.conversation_id === runtime.conversation_id, 120000, 'turn');
  await sleep(300);
  return { accepted: acc.accepted, stop: fin.stop_reason };
}

async function otidCount(client, conv, otid) {
  const listed = await client.request({ type: 'conversation_messages_list', conversation_id: conv, query: { limit: 1000, order: 'desc' } }, { timeoutMs: 60000 });
  return (listed.messages ?? []).filter((m) => m.otid === otid).length;
}

const result = { setup: {}, grow: {}, append_kills: [], rewrite_kills: [] };
let client = await connect('crashA-setup');
const agent = await client.request({ type: 'runtime_start', create_agent: { body: { name: 'crash-agent', model: MODEL, system: 'Crash test agent.' }, pin_global: false },
  create_conversation: { body: {} }, mode: 'strict', client_info: { name: 'crashA' }, force_device_status: true, wait_for_replay: true }, { timeoutMs: 60000 });
const runtime = agent.runtime;
const conv = runtime.conversation_id;
await client.request({ type: 'update_toolset', runtime, toolset_preference: 'none' });
const upd = await client.request({ type: 'conversation_update', conversation_id: conv, body: { context_window_limit: 20000000 } });
result.setup = { runtime, context_window_limit_set: upd.success, error: upd.error ?? null };

// Grow the transcript so the rewrite window is measurable.
const filler = 'Synthetic filler paragraph for crash testing. '.repeat(Math.ceil(Number(growBytes) / 46)).slice(0, Number(growBytes));
const t0 = Date.now();
for (let i = 0; i < Number(growTurns); i++) await turn(client, runtime, `grow ${i}: ${filler}`, `grow-${i}`);
result.grow = { turns: Number(growTurns), ms: Date.now() - t0, integrity: integrity(conv) };
client.close();

// A: SIGKILL shortly after a user message is sent (append window).
for (let i = 0; i < Number(appendKills); i++) {
  client = await connect(`crashA-${i}`);
  await client.request({ type: 'runtime_start', agent_id: runtime.agent_id, conversation_id: conv, mode: 'strict', client_info: { name: 'crashA' }, wait_for_replay: true }, { timeoutMs: 60000 });
  const otid = `crashA-append-${i}`;
  const delay = Math.floor(Math.random() * 25);
  client.send({ type: 'input', runtime, request_id: `r-${i}`, payload: { kind: 'create_message', messages: [{ role: 'user', content: `append probe ${i}`, client_message_id: otid }] } });
  await sleep(delay);
  const killed = lettactl('kill', '--signal', 'KILL');
  client.kill();
  lettactl('start');
  const check = integrity(conv);
  client = await connect(`crashA-${i}-after`);
  await client.request({ type: 'runtime_start', agent_id: runtime.agent_id, conversation_id: conv, mode: 'strict', client_info: { name: 'crashA' }, wait_for_replay: true }, { timeoutMs: 60000 });
  const count = await otidCount(client, conv, otid);
  let usable = null;
  if (i % 5 === 4) usable = await turn(client, runtime, `usable check ${i}`, `crashA-usable-${i}`);
  client.close();
  result.append_kills.push({ i, delay_ms: delay, namespace_gone: killed.namespace_gone, otid_present: count, unparseable: check.unparseable_lines.length,
    dup_ids: check.duplicate_message_ids.length, dup_otids: check.duplicate_user_otids.length, no_return: check.tool_calls_without_return.length,
    conversation_json: check.conversation_json, in_ctx_missing: (check.in_context_missing_from_transcript ?? []).length, bytes: check.bytes, usable });
}

// Rewrite window: conversation_update rewrites the whole transcript (writeFileSync, truncate + write).
for (let j = 0; j < Number(rewriteKills); j++) {
  client = await connect(`crashR-${j}`);
  const before = integrity(conv);
  const delay = Math.floor(Math.random() * 20);
  client.send({ type: 'conversation_update', request_id: `u-${j}`, conversation_id: conv, body: { summary: `rewrite probe ${j}` } });
  await sleep(delay);
  const killed = lettactl('kill', '--signal', 'KILL');
  client.kill();
  const after = integrity(conv);
  lettactl('start');
  client = await connect(`crashR-${j}-after`);
  const listed = await client.request({ type: 'conversation_messages_list', conversation_id: conv, query: { limit: 5, order: 'desc' } }, { timeoutMs: 60000 }).catch((e) => ({ error: String(e) }));
  client.close();
  result.rewrite_kills.push({ j, delay_ms: delay, namespace_gone: killed.namespace_gone, bytes_before: before.bytes, bytes_after: after.bytes,
    messages_before: before.messages, messages_after: after.messages, unparseable_after: (after.unparseable_lines ?? []).length,
    conversation_json_after: after.conversation_json, readable_after_restart: !listed.error && Array.isArray(listed.messages) });
}
result.final = integrity(conv);
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
const lost = result.rewrite_kills.filter((r) => r.messages_after < r.messages_before || r.unparseable_after > 0 || r.conversation_json_after !== 'ok');
console.log(JSON.stringify({ setup: result.setup, grow: { ms: result.grow.ms, bytes: result.grow.integrity.bytes, messages: result.grow.integrity.messages },
  append: { n: result.append_kills.length, present: result.append_kills.filter((a) => a.otid_present === 1).length, absent: result.append_kills.filter((a) => a.otid_present === 0).length,
    duplicated: result.append_kills.filter((a) => a.otid_present > 1).length, corrupt: result.append_kills.filter((a) => a.unparseable || a.conversation_json !== 'ok' || a.in_ctx_missing).length,
    usable_checks: result.append_kills.filter((a) => a.usable).map((a) => a.usable.stop) },
  rewrite: { n: result.rewrite_kills.length, damaged: lost.length, examples: lost.slice(0, 5) }, final: { bytes: result.final.bytes, messages: result.final.messages, unparseable: result.final.unparseable_lines.length } }, null, 1));
process.exit(0);
