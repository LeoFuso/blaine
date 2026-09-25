// Crash test D: projector delivery under process death.
//   D1 projector dies right after input_accepted (before read-back confirmation)
//   D2 projection queued behind a busy turn; App Server SIGKILLed before it runs
//   D3 projection queued behind a busy turn; projector dies and restarts while the
//      item is still only in Letta's in-memory queue (read-back says "absent")
// Each case uses its own conversation + one completed Blaine summary Task.
// node src/probe12_projector_crash.mjs STATE PORT AGENT_ID BINDINGS CASE OUT
import { execFileSync, spawn } from 'node:child_process';
import { appendFileSync, readFileSync, writeFileSync } from 'node:fs';
import { Human } from './human.mjs';
import { createBoundConversation } from './setup.mjs';
import { V2Client, stateToken } from './v2client.mjs';

const [state, port, agentId, bindingsPath, which, out] = process.argv.slice(2);
const HERE = new URL('.', import.meta.url).pathname;
const HARNESS = new URL('../harness/', import.meta.url).pathname;
const base = bindingsPath.replace(/\.json$/, '');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const jsonl = (p) => { try { return readFileSync(p, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)); } catch { return []; } };
const lettactl = (...args) => JSON.parse(execFileSync('python3', [`${HARNESS}lettactl.py`, ...args, state]).toString().trim().split('\n').at(-1));
const enqueue = (item) => appendFileSync(`${state}/work/hostile-queue.jsonl`, JSON.stringify(item) + '\n');
const until = async (fn, ms, what) => { const end = Date.now() + ms; while (Date.now() < end) { const v = await fn(); if (v) return v; await sleep(250); } throw new Error(`timeout: ${what}`); };
const projector = (name, extra = []) => new Promise((resolve) => {
  const p = spawn('node', [`${HERE}projector.mjs`, '--state', state, '--port', port, '--bindings', bindingsPath, '--once', '--name', name, ...extra], { stdio: 'ignore' });
  p.on('exit', (code) => resolve(code));
});
async function connect(name) { for (let i = 0; i < 60; i++) { try { const c = new V2Client({ port: Number(port), token: stateToken(state), name, trace: `${state}/logs/${name}-trace.jsonl` }); await c.connect(3000); return c; } catch { await sleep(250); } } throw new Error('connect'); }

const result = { case: which };
const setup = await connect(`D-${which}-setup`);
const runtime = await createBoundConversation(setup, agentId, bindingsPath, 'spike-project');
const conv = runtime.conversation_id;
setup.close();
await sleep(2500);
let human = new Human({ state, port, name: `D-${which}-human`, approveDelayMs: 500, approve: (req) => (req.tool_name.startsWith('blaine_') ? { behavior: 'allow' } : { behavior: 'deny', message: 'no' }) });
await human.start({ agent_id: agentId, conversation_id: conv, mode: 'strict' });
const ledgerBefore = jsonl(`${base}.ledger.jsonl`).length;
enqueue({ tool_call: { name: 'blaine_task_create', arguments: { kind: 'summary', text: `Synthetic projector crash text ${which}.` } } });
enqueue({ text: 'Task submitted.' });
await human.say('Create a Blaine summary Task for my synthetic text.', { timeoutMs: 120000 });
const task = await until(() => jsonl(`${base}.ledger.jsonl`).slice(ledgerBefore).find((e) => e.event === 'created' && e.conversation_id === conv)?.task_id, 60000, 'task');
result.task = task;
const key = `${task}:terminal:COMPLETED`;
const deliveries = () => jsonl(`${base}.deliveries.jsonl`).filter((e) => e.key === key);
const busy = async (ms) => { enqueue({ text: 'Long synthetic answer.', delay_ms: ms }); await human.say('Please think about this for a while.', { wait: false }); await sleep(1500); };

if (which === 'D1') {
  result.first_projector_exit = await projector(`proj-${which}-1`, ['--crash-after-send']);
  await sleep(2000);
  result.second_projector_exit = await projector(`proj-${which}-2`);
} else if (which === 'D2') {
  await busy(15000);
  result.first_projector_exit = await projector(`proj-${which}-1`, ['--crash-after-send']);
  result.disposition = deliveries().find((e) => e.event === 'input_accepted')?.disposition;
  result.kill = lettactl('kill', '--signal', 'KILL');
  human.client.kill();
  lettactl('start');
  await sleep(2000);
  result.second_projector_exit = await projector(`proj-${which}-2`);
} else if (which === 'D3') {
  await busy(15000);
  result.first_projector_exit = await projector(`proj-${which}-1`, ['--crash-after-send']);
  result.disposition = deliveries().find((e) => e.event === 'input_accepted')?.disposition;
  result.second_projector_exit = await projector(`proj-${which}-2`); // item still in Letta's in-memory queue
}
await sleep(20000); // let the busy turn and any queued projection turns finish
const c = await connect(`D-${which}-check`);
const listed = await c.request({ type: 'conversation_messages_list', conversation_id: conv, query: { limit: 500, order: 'asc' } }, { timeoutMs: 60000 });
const cmid = deliveries().find((e) => e.cmid)?.cmid;
result.visible_projection_count = (listed.messages ?? []).filter((m) => m.otid === cmid).length;
result.delivery_log = deliveries().map((e) => ({ event: e.event, c: e.c, disposition: e.disposition ?? undefined, via: e.via ?? undefined }));
result.integrity = JSON.parse(execFileSync('python3', [`${HARNESS}integrity.py`, state, conv]).toString().trim());
c.close();
human.close();
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify({ case: which, disposition: result.disposition, visible_projection_count: result.visible_projection_count, delivery_log: result.delivery_log,
  dup_otids: result.integrity.duplicate_user_otids, unparseable: result.integrity.unparseable_lines.length }, null, 1));
process.exit(0);
