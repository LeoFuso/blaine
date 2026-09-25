// Crash test B: SIGKILL the App Server while a blaine_task_create call is in flight
// (Blaine already created the Task; the controller is holding its reply), restart,
// resume the conversation, and count Blaine Tasks for the request.
//
// node src/probe06_turn_crash.mjs STATE PORT AGENT_ID BINDINGS CONVERSATION_ID LABEL OUT
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { Human, brief } from './human.mjs';

const [state, port, agentId, bindingsPath, conversationId, label, out] = process.argv.slice(2);
const HARNESS = new URL('../harness/', import.meta.url).pathname;
const ledgerPath = bindingsPath.replace(/\.json$/, '') + '.ledger.jsonl';
const ledger = () => readFileSync(ledgerPath, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const lettactl = (...args) => JSON.parse(execFileSync('python3', [`${HARNESS}lettactl.py`, ...args, state], { env: process.env }).toString().trim().split('\n').at(-1));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const until = async (fn, ms, what) => { const end = Date.now() + ms; while (Date.now() < end) { const v = fn(); if (v) return v; await sleep(250); } throw new Error(`timeout: ${what}`); };
const approveBlaine = (req) => (req.tool_name.startsWith('blaine_') ? { behavior: 'allow' } : { behavior: 'deny', message: 'non-Blaine tool denied' });
const timeline = [];
const mark = (event, extra = {}) => timeline.push({ t: new Date().toISOString(), event, ...extra });

const MODE = process.env.CRASH_MODE ?? 'full'; // full | resume (continue an already-crashed conversation)
const ledgerStart = Number(process.env.LEDGER_START ?? ledger().length);
let human;
if (MODE === 'full') {
  human = new Human({ state, port, name: `crashB-${label}-1`, approve: approveBlaine });
  await human.start({ agent_id: agentId, conversation_id: conversationId, mode: 'strict' });
  const question = `Approve the synthetic vendor renewal ${label.toUpperCase()} for Q4?`;
  mark('user_request_sent');
  await human.say(`Please open a formal Blaine decision with exactly this question: "${question}"`, { wait: false });
  const fault = await until(() => ledger().slice(ledgerStart).find((e) => e.event === 'fault_delay'), 300000, 'controller fault_delay');
  mark('controller_created_task_and_is_holding_reply', { tool_call_id: fault.tool_call_id });
  const killed = lettactl('kill', '--signal', 'KILL');
  mark('app_server_sigkill', killed);
  human.client.kill();
  await sleep(1000);
  const started = lettactl('start');
  mark('app_server_restarted', started);
  const killedAt = new Date(killed.at * 1000).toISOString();
  await until(() => ledger().slice(ledgerStart).some((e) => e.event === 'registered' && e.runtimes > 0 && e.t > killedAt), 30000, 'controller re-registered');
  mark('controller_reregistered');
}

human = new Human({ state, port, name: `crashB-${label}-2`, approve: approveBlaine });
const resumed = await human.start({ agent_id: agentId, conversation_id: conversationId, mode: 'strict', recover_approvals: true });
mark('client_reattached', { runtime: resumed.runtime });
// Owner resume: continue the interrupted turn now (stale denial -> model may re-issue).
const deltas = [];
human.client.on('frame', (f) => { if (f.runtime?.conversation_id === conversationId) deltas.push(f); });
await human.client.request({ type: 'sync', runtime: resumed.runtime, recover_approvals: true, resume_interrupted_turn: true }, { timeoutMs: 60000 });
mark('owner_sync_resume_sent');
try {
  await human.client.waitFor((f) => f.type === "turn_finished" && f.runtime?.conversation_id === conversationId, Number(process.env.RESUME_WAIT_MS ?? 300000), "resumed turn");
  mark('resumed_turn_finished');
} catch (error) { mark('no_resumed_turn', { error: String(error) }); }
await sleep(3000);
// A natural follow-up from the user, as would happen after a visible interruption.
const follow = await human.say('Did that decision get opened? If not, open it now.', { timeoutMs: 300000 });
mark('followup_turn_finished', { stop_reason: follow.finished?.stop_reason });
await sleep(25000); // let any held controller replies land

const mine = ledger().slice(ledgerStart);
const created = mine.filter((e) => e.event === 'created');
const tasks = [...new Set(created.map((e) => e.task_id))];
const transcript = await human.transcript(400);
const result = { label, conversation_id: conversationId, identity: mine.find((e) => e.event === 'identity')?.mode,
  tool_calls: mine.filter((e) => e.event === 'tool_call').map((e) => ({ tool_call_id: e.tool_call_id, tool: e.tool, input: e.input })),
  identities: mine.filter((e) => e.event === 'identity').map((e) => ({ tool_call_id: e.tool_call_id, request_id: e.request_id, anchor: e.anchor?.id ?? null })),
  created: created.map((e) => ({ tool_call_id: e.tool_call_id, task_id: e.task_id, submission: e.submission })),
  converged: mine.filter((e) => e.event === 'converged').length,
  distinct_blaine_tasks: tasks.length, tasks, timeline,
  approvals: human.approvals.map((a) => ({ tool: a.tool, input: a.input, ack: a.ack ?? null })),
  transcript: brief(transcript), resumed_deltas: deltas.length };
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify({ label, identity: result.identity, tool_calls: result.tool_calls.length, created: result.created, distinct_blaine_tasks: tasks.length, converged: result.converged, timeline }, null, 1));
human.close();
process.exit(0);
