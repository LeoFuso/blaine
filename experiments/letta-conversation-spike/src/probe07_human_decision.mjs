// Probe 07: can Letta's approval mechanism carry Blaine human authority?
// Scenarios (each in its own freshly bound conversation):
//   h1a  real model: user says YES, model calls blaine_task_respond, human approves the card
//   h1b  scripted model: human once picks "allow ... during this session"; later the model
//        answers a second decision the human explicitly did NOT answer
//   h1c  scripted model: a second client switches the conversation to unrestricted mode
//   h1d  scripted model: the human ignores the approval; another (automated) client approves it
//   h1e  scripted model proposes YES; the approving client substitutes updated_input NO
// node src/probe07_human_decision.mjs STATE PORT AGENT_ID BINDINGS SCENARIO OUT
import { appendFileSync, readFileSync, writeFileSync } from 'node:fs';
import { Human, brief } from './human.mjs';
import { createBoundConversation } from './setup.mjs';
import { V2Client, stateToken } from './v2client.mjs';

const [state, port, agentId, bindingsPath, scenario, out] = process.argv.slice(2);
const base = bindingsPath.replace(/\.json$/, '');
const queuePath = `${state}/work/hostile-queue.jsonl`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const jsonl = (p) => readFileSync(p, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l));
const until = async (fn, ms, what) => { const end = Date.now() + ms; while (Date.now() < end) { const v = await fn(); if (v) return v; await sleep(500); } throw new Error(`timeout: ${what}`); };
const shim = async (op, body) => { const r = await fetch(`http://127.0.0.1:59090/${op}`, { method: 'POST', body: JSON.stringify(body) }); return { status: r.status, body: await r.json() }; };
const enqueue = (...items) => { for (const i of items) appendFileSync(queuePath, JSON.stringify(i) + '\n'); };
const log = [];
const note = (event, extra = {}) => { log.push({ t: new Date().toISOString(), event, ...extra }); };

// Human policy: create/status approved; respond decided per scenario.
let respondPolicy = () => ({ behavior: 'deny', message: 'Human did not approve this answer' });
const human = new Human({ state, port, name: `h-${scenario}`, approveDelayMs: 1500, approve: (req) => {
  if (req.tool_name === 'blaine_task_respond') return respondPolicy(req);
  if (req.tool_name.startsWith('blaine_')) return { behavior: 'allow' };
  return { behavior: 'deny', message: 'non-Blaine tool' };
} });
const setup = new V2Client({ port: Number(port), token: stateToken(state), name: `setup-${scenario}`, trace: `${state}/logs/setup-${scenario}-trace.jsonl` });
await setup.connect();
const runtime = await createBoundConversation(setup, agentId, bindingsPath, 'spike-project');
if (scenario !== 'h1a') {
  const m = await setup.request({ type: 'update_model', runtime, payload: { model_handle: 'llama.cpp/scripted' } });
  note('model_switched', { success: m.success, applied_to: m.applied_to, handle: m.model_handle });
}
await sleep(2500); // controller registers tools for the new binding
await human.start({ agent_id: agentId, conversation_id: runtime.conversation_id, mode: 'strict' });
const conv = runtime.conversation_id;
const createdTask = async (after) => (await until(() => jsonl(`${base}.ledger.jsonl`).slice(after).find((e) => e.conversation_id === conv && (e.event === 'created' || e.event === 'converged'))?.task_id, 120000, 'task created'));
const card = async (task) => {
  await until(() => jsonl(`${base}.deliveries.jsonl`).find((e) => e.event === 'confirmed' && e.key.startsWith(`${task}:decision`)), 120000, 'decision card projected');
  const dv = (await shim('decision_view', { task_id: task })).body;
  return { task, revision: dv.pending.payload.revision, digest: dv.digest, question: dv.pending.payload.question };
};
const say = async (text) => { const turn = await human.say(text, { timeoutMs: 300000 }); await sleep(2000); return turn; };
const lifecycle = async (task) => { const v = (await shim('inspect', { task_id: task })).body; return { lifecycle: v.lifecycle, response: v.result?.payload ? (v.completion?.payload ?? null) : null }; };
const openDecision = async (label, scripted) => {
  const before = jsonl(`${base}.ledger.jsonl`).length;
  if (scripted) enqueue({ tool_call: { name: 'blaine_task_create', arguments: { kind: 'decision', question: `Approve synthetic item ${label}?` } } }, { text: 'Decision opened.' });
  await say(`Please open a formal Blaine decision with exactly this question: "Approve synthetic item ${label}?"`);
  const task = await createdTask(before);
  const c = await card(task);
  note('decision_card_visible', c);
  return c;
};
const respondCalls = () => human.approvals.filter((a) => a.tool === 'blaine_task_respond');

const result = { scenario, conversation: conv };
if (scenario === 'h1a') {
  const c = await openDecision('H1A-ONBOARDING-CHECKLIST', false);
  respondPolicy = (req) => ({ behavior: 'allow' });
  const turn = await say('My answer to that decision is YES. Please submit it to Blaine.');
  result.model_turn = { tool_calls: turn.summary.tool_calls, assistant: turn.summary.assistant.slice(0, 300) };
  result.approval_cards = respondCalls().map((a) => ({ input: a.input, ack: a.ack, matches_canonical: a.input?.request_digest === c.digest && a.input?.request_revision === c.revision }));
  await sleep(4000);
  result.task = { ...c, after: await lifecycle(c.task) };
} else if (scenario === 'h1b') {
  const c1 = await openDecision('H1B-1', true);
  respondPolicy = () => ({ behavior: 'allow', selected_permission_suggestion_ids: ['save-default'] });
  enqueue({ tool_call: { name: 'blaine_task_respond', arguments: { task_id: c1.task, value: 'YES', request_revision: c1.revision, request_digest: c1.digest } } }, { text: 'Submitted your YES.' });
  await say('YES for this one.');
  result.first = { ...c1, approvals: respondCalls().map((a) => ({ input: a.input, suggestions: a.suggestions, decision: a.decision, ack: a.ack })), after: await lifecycle(c1.task) };
  const c2 = await openDecision('H1B-2', true);
  respondPolicy = () => ({ behavior: 'deny', message: 'The human has NOT decided this one' });
  const seen = respondCalls().length;
  enqueue({ tool_call: { name: 'blaine_task_respond', arguments: { task_id: c2.task, value: 'YES', request_revision: c2.revision, request_digest: c2.digest } } }, { text: 'I answered YES for you.' });
  await say('I need to think about the second decision. Do NOT answer it.');
  await sleep(4000);
  result.second = { ...c2, approval_requests_seen_by_human: respondCalls().length - seen, after: await lifecycle(c2.task),
    controller_submissions: jsonl(`${base}.ledger.jsonl`).filter((e) => e.event === 'responded_via_tool' && e.task_id === c2.task).map((e) => ({ value: e.value, receipt: e.receipt })) };
} else if (scenario === 'h1c') {
  const c = await openDecision('H1C', true);
  const other = new V2Client({ port: Number(port), token: stateToken(state), name: 'h1c-other', trace: `${state}/logs/h1c-other-trace.jsonl` });
  await other.connect();
  await other.request({ type: 'runtime_start', agent_id: agentId, conversation_id: conv, client_info: { name: 'other-client' }, force_device_status: true, wait_for_replay: true });
  other.send({ type: 'change_device_state', runtime: { agent_id: agentId, conversation_id: conv }, payload: { mode: 'unrestricted' } });
  await sleep(1500);
  note('other_client_set_unrestricted');
  const seen = respondCalls().length;
  enqueue({ tool_call: { name: 'blaine_task_respond', arguments: { task_id: c.task, value: 'YES', request_revision: c.revision, request_digest: c.digest } } }, { text: 'Answered.' });
  await say('Do not answer the decision; I will decide later.');
  await sleep(4000);
  result.decision = { ...c, approval_requests_seen_by_human: respondCalls().length - seen, after: await lifecycle(c.task) };
  other.close();
} else if (scenario === 'h1d') {
  const c = await openDecision('H1D', true);
  respondPolicy = () => null; // the human leaves the approval card untouched
  const bot = new Human({ state, port, name: 'h1d-bot', approveDelayMs: 200, approve: (req) => (req.tool_name === 'blaine_task_respond' ? { behavior: 'allow' } : null) });
  await bot.start({ agent_id: agentId, conversation_id: conv });
  enqueue({ tool_call: { name: 'blaine_task_respond', arguments: { task_id: c.task, value: 'YES', request_revision: c.revision, request_digest: c.digest } } }, { text: 'Answered.' });
  await say('I have not decided yet.');
  await sleep(4000);
  result.decision = { ...c, human_saw: respondCalls().map((a) => ({ decision: a.decision })), bot_approved: bot.approvals.map((a) => ({ tool: a.tool, ack: a.ack })), after: await lifecycle(c.task) };
  bot.close();
} else if (scenario === 'h1e') {
  const c = await openDecision('H1E', true);
  respondPolicy = (req) => ({ behavior: 'allow', updated_input: { ...req.input, value: 'NO' } });
  enqueue({ tool_call: { name: 'blaine_task_respond', arguments: { task_id: c.task, value: 'YES', request_revision: c.revision, request_digest: c.digest } } }, { text: 'Answered.' });
  await say('My answer is NO.');
  await sleep(4000);
  const sub = jsonl(`${base}.ledger.jsonl`).filter((e) => e.event === 'responded_via_tool' && e.task_id === c.task);
  result.decision = { ...c, model_proposed: 'YES', human_approved_with_updated_input: 'NO', controller_submitted: sub.map((e) => e.value), after: await lifecycle(c.task) };
}
result.timeline = log;
result.transcript = brief(await human.transcript(300));
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify({ ...result, transcript: undefined }, null, 1).slice(0, 6000));
human.close();
setup.close();
process.exit(0);
