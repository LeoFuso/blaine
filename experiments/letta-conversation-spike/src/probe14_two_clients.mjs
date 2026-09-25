// Probe 14: two independent clients on one conversation (scripted model, deterministic timing).
// node src/probe14_two_clients.mjs STATE PORT AGENT_ID BINDINGS OUT
import { appendFileSync, writeFileSync } from 'node:fs';
import { createBoundConversation } from './setup.mjs';
import { V2Client, stateToken } from './v2client.mjs';
import { brief } from './human.mjs';

const [state, port, agentId, bindingsPath, out] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const enqueue = (item) => appendFileSync(`${state}/work/hostile-queue.jsonl`, JSON.stringify(item) + '\n');
const mk = async (name) => { const c = new V2Client({ port: Number(port), token: stateToken(state), name, trace: `${state}/logs/${name}-trace.jsonl` }); await c.connect(); return c; };

const setup = await mk('p14-setup');
const runtime = await createBoundConversation(setup, agentId, bindingsPath, 'spike-project');
const conv = runtime.conversation_id;
setup.close();
const start = (c) => c.request({ type: 'runtime_start', agent_id: agentId, conversation_id: conv, mode: 'strict', client_info: { name: c.name }, force_device_status: true, wait_for_replay: true }, { timeoutMs: 60000 });
const send = (c, text, cmid) => c.request({ type: 'input', runtime, payload: { kind: 'create_message', messages: [{ role: 'user', content: text, client_message_id: cmid }] } }, { type: 'input_accepted' });
const seen = { A: [], B: [], A2: [] };
const watch = (c, key) => c.on('frame', (f) => { if (f.runtime?.conversation_id === conv && ['turn_finished', 'update_queue', 'input_accepted'].includes(f.type)) seen[key].push({ t: Date.now(), type: f.type, stop: f.stop_reason, queue: f.queue?.map((q) => q.client_message_id), removed: f.removed, disp: f.disposition }); if (f.type === 'stream_delta' && f.runtime?.conversation_id === conv && f.delta?.message_type === 'assistant_message') seen[key].push({ t: Date.now(), type: 'assistant_delta' }); });
let A = await mk('p14-A'); const B = await mk('p14-B');
await start(A); await start(B); watch(A, 'A'); watch(B, 'B');
const result = { conversation: conv, steps: [] };
const step = (event, extra = {}) => result.steps.push({ t: new Date().toISOString(), event, ...extra });

// 1) A starts a long turn; B sends during it.
enqueue({ text: 'Reply to M1 (slow).', delay_ms: 8000 });
enqueue({ text: 'Reply to M2.' });
step('A_send_M1', { ack: await send(A, 'M1 from client A', 'p14-M1') });
await sleep(1500);
step('B_send_M2_during_turn', { ack: await send(B, 'M2 from client B', 'p14-M2') });
// 2) A disconnects abruptly mid-turn, then reconnects as a new connection and syncs.
await sleep(1000);
A.kill();
step('A_socket_killed_mid_turn');
await sleep(1500);
A = await mk('p14-A2'); watch(A, 'A2');
await start(A);
step('A_reconnected', { sync: (await A.request({ type: 'sync', runtime, recover_approvals: true }, { timeoutMs: 30000 })).success });
// wait for both turns
const fin = [];
const done = new Promise((resolve) => { const h = (f) => { if (f.type === 'turn_finished' && f.runtime?.conversation_id === conv) { fin.push(f.stop_reason); if (fin.length >= 2) { B.off('frame', h); resolve(); } } }; B.on('frame', h); });
await Promise.race([done, sleep(60000)]);
step('turns_finished_seen_by_B', { stops: fin });
// 3) A queued message whose sender disconnects before it runs.
enqueue({ text: 'Reply to M3 (slow).', delay_ms: 6000 });
enqueue({ text: 'Reply to M4.' });
step('A_send_M3', { ack: await send(A, 'M3 from client A', 'p14-M3') });
await sleep(1000);
const C = await mk('p14-C'); await start(C);
step('C_send_M4_queued', { ack: await send(C, 'M4 from short-lived client C', 'p14-M4') });
await sleep(300);
C.kill();
step('C_disconnected_while_M4_queued');
await sleep(12000);
// 4) Convergence: both clients read the same ordered history.
const hist = async (c) => brief((await c.request({ type: 'conversation_messages_list', conversation_id: conv, query: { limit: 200, order: 'asc' } }, { timeoutMs: 60000 })).messages ?? []);
const hA = await hist(A); const hB = await hist(B);
result.history_A = hA.map((m) => `${m.type}:${m.otid ?? ''}:${m.text.slice(0, 40)}`);
result.converged = JSON.stringify(hA.map((m) => m.id)) === JSON.stringify(hB.map((m) => m.id));
result.M4_present = hA.some((m) => m.otid === 'p14-M4');
result.frames = { A: seen.A, B: seen.B, A2: seen.A2 };
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify({ steps: result.steps, converged: result.converged, M4_present: result.M4_present, history: result.history_A,
  B_queue_events: seen.B.filter((e) => e.type === 'update_queue' && (e.queue?.length || e.removed?.length)).map((e) => ({ queue: e.queue, removed: e.removed })),
  B_assistant_deltas: seen.B.filter((e) => e.type === 'assistant_delta').length, A2_assistant_deltas: seen.A2.filter((e) => e.type === 'assistant_delta').length }, null, 1));
A.close(); B.close();
process.exit(0);
