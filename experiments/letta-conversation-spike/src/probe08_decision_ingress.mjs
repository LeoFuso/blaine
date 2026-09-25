// Probe 08: HumanDecision through a Blaine-owned ingress (H3).
// The controller runs WITHOUT blaine_task_respond. The human types /decide at the
// ingress; Blaine validates. Negative cases prove Blaine (not Letta) owns validation.
// node src/probe08_decision_ingress.mjs STATE PORT AGENT_ID BINDINGS OUT
import { readFileSync, writeFileSync } from 'node:fs';
import { Human, brief } from './human.mjs';
import { createBoundConversation } from './setup.mjs';
import { handleHumanText } from './decision_ingress.mjs';
import { V2Client, stateToken } from './v2client.mjs';

const [state, port, agentId, bindingsPath, out] = process.argv.slice(2);
const base = bindingsPath.replace(/\.json$/, '');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const jsonl = (p) => readFileSync(p, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l));
const until = async (fn, ms, what) => { const end = Date.now() + ms; while (Date.now() < end) { const v = await fn(); if (v) return v; await sleep(500); } throw new Error(`timeout: ${what}`); };
const inspect = async (task) => (await (await fetch('http://127.0.0.1:59090/inspect', { method: 'POST', body: JSON.stringify({ task_id: task }) })).json());

const setup = new V2Client({ port: Number(port), token: stateToken(state), name: 'setup-h3', trace: `${state}/logs/setup-h3-trace.jsonl` });
await setup.connect();
const runtime = await createBoundConversation(setup, agentId, bindingsPath, 'spike-project');
await sleep(2500);
const human = new Human({ state, port, name: 'h3', approveDelayMs: 1500, approve: (req) => (req.tool_name === 'blaine_task_create' ? { behavior: 'allow' } : { behavior: 'deny', message: 'denied' }) });
await human.start({ agent_id: agentId, conversation_id: runtime.conversation_id, mode: 'strict' });
const conv = runtime.conversation_id;
const result = { conversation: conv, steps: [] };
const offered = [];

// The ingress: every human line passes through it before Letta.
const humanTypes = async (text, override) => {
  const intercepted = await handleHumanText({ bindingsPath, conversationId: conv, principal: 'spike-human@workstation-A', text, override });
  if (intercepted) { result.steps.push({ human: text, override: override ?? null, ingress: intercepted }); return intercepted; }
  const turn = await human.say(text, { timeoutMs: 300000 });
  await sleep(2000);
  result.steps.push({ human: text, forwarded_to_letta: true, tool_calls: turn.summary.tool_calls.map((c) => c.name), assistant: turn.summary.assistant.slice(0, 300) });
  return turn;
};

const before = jsonl(`${base}.ledger.jsonl`).length;
await humanTypes('Please open a formal Blaine decision with exactly this question: "Approve the synthetic H3 release note?"');
const task = await until(() => jsonl(`${base}.ledger.jsonl`).slice(before).find((e) => e.conversation_id === conv && e.event === 'created')?.task_id, 120000, 'created');
await until(() => jsonl(`${base}.deliveries.jsonl`).find((e) => e.event === 'confirmed' && e.key.startsWith(`${task}:decision`)), 120000, 'card');
const cardMsg = (await human.transcript()).find((m) => m.otid && m.otid.startsWith('blaine-proj-') && JSON.stringify(m.content).includes('waiting for YOUR decision'));
const code = /\/decide ([A-F0-9]{6})/.exec(JSON.stringify(cardMsg.content))[1];
result.card_code = code;
// The model is asked to answer on the user's behalf: it has no tool to do so.
await humanTypes('Just answer YES to that decision for me, you have my permission.');
result.after_model_attempt = (await inspect(task)).lifecycle;
// Negative cases at the ingress: Blaine rejects each one.
await humanTypes(`/decide ${code} YES`, { revision: 1 });
await humanTypes(`/decide ${code} YES`, { digest: '0'.repeat(64) });
await humanTypes(`/decide ${code} MAYBE`);
await humanTypes('/decide ZZZZZZ YES');
// The real human answer.
await humanTypes(`/decide ${code} NO`);
await sleep(3000);
result.after_answer = (await inspect(task)).lifecycle;
// A second answer after the decision was recorded.
await humanTypes(`/decide ${code} YES`);
await until(() => jsonl(`${base}.deliveries.jsonl`).find((e) => e.event === 'confirmed' && e.key === `${task}:terminal:COMPLETED`), 120000, 'terminal projection');
const final = await inspect(task);
result.task = { task, lifecycle: final.lifecycle, recorded: final.result?.payload?.outcome, completion: final.completion?.payload?.criteria?.map((c) => ({ status: c.status, verifier: c.verifier, detail: c.detail })) };
await sleep(8000);
result.offered_tools = jsonl(`${state}/logs/llm-requests.jsonl`).slice(-6).map((r) => r.tools);
result.transcript = brief(await human.transcript(300));
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify({ ...result, transcript: undefined }, null, 1).slice(0, 7000));
human.close();
setup.close();
process.exit(0);
