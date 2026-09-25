// Probe 18: one human line of work in one Letta Conversation, end to end (real model).
//   desktop-like client: discussion without Tasks, then a mixed request (answer + 2 Tasks)
//   pause: ALL clients disconnected; summary Task completes, decision answered at the
//          Blaine ingress (no Letta client attached); projector delivers both outcomes
//   resume from another interface (letta-acp session/load, override build) and continue
//   return to the first client: converged history
// node src/probe18_line_of_work.mjs STATE PORT AGENT_ID BINDINGS OUT
// Env: ACP_SDK, ACP_BIN, ACP_HOME (as probe15)
import { readFileSync, writeFileSync } from 'node:fs';
import { Human, brief } from './human.mjs';
import { createBoundConversation } from './setup.mjs';
import { handleHumanText } from './decision_ingress.mjs';
import { withAcp } from './acp_client.mjs';
import { V2Client, stateToken } from './v2client.mjs';

const [state, port, agentId, bindingsPath, out] = process.argv.slice(2);
const base = bindingsPath.replace(/\.json$/, '');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const jsonl = (p) => readFileSync(p, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l));
const until = async (fn, ms, what) => { const end = Date.now() + ms; while (Date.now() < end) { const v = await fn(); if (v) return v; await sleep(1000); } throw new Error(`timeout: ${what}`); };
const inspect = async (task) => (await (await fetch('http://127.0.0.1:59090/inspect', { method: 'POST', body: JSON.stringify({ task_id: task }) })).json());
const timeline = [];
const mark = (event, extra = {}) => { timeline.push({ t: new Date().toISOString(), event, ...extra }); };

const setup = new V2Client({ port: Number(port), token: stateToken(state), name: 'lw-setup', trace: `${state}/logs/lw-setup-trace.jsonl` });
await setup.connect();
const runtime = await createBoundConversation(setup, agentId, bindingsPath, 'project-vendor-review');
setup.close();
const conv = runtime.conversation_id;
mark('conversation_bound', { conversation: conv, project: 'project-vendor-review' });
await sleep(2500);

// Session 1: desktop-like client.
let desk = new Human({ state, port, name: 'lw-desktop', approveDelayMs: 1500, approve: (r) => (r.tool_name.startsWith('blaine_task_') && r.tool_name !== 'blaine_task_respond' ? { behavior: 'allow' } : { behavior: 'deny', message: 'no' }) });
await desk.start({ agent_id: agentId, conversation_id: conv, mode: 'strict' });
const s1 = [];
for (const text of [
  'Let us work on the synthetic Q4 vendor review. Three vendors: Acme Storage, Birch Analytics, Cobalt Networks. No action yet; what criteria would you use to compare them?',
  'Good. Birch Analytics had two synthetic outages this quarter. Does that change your view? Just discuss.',
]) { const t = await desk.say(text); await sleep(2500); s1.push({ user: text.slice(0, 60), tools: t.summary.tool_calls.map((c) => c.name), assistant: t.summary.assistant.slice(0, 220) }); }
mark('discussion_without_tasks', { turns: s1.length, tool_calls: s1.flatMap((x) => x.tools) });
const l0 = jsonl(`${base}.ledger.jsonl`).length;
const mixed = await desk.say('Two things. First, in one sentence, which vendor looks riskiest? Second, please create a Blaine summary Task for this text: "Acme 99.95%, Birch 99.2%, Cobalt 99.9% synthetic uptime." and open a formal Blaine decision with exactly this question: "Approve renewing Birch Analytics for Q4?"');
await sleep(3000);
const created = jsonl(`${base}.ledger.jsonl`).slice(l0).filter((e) => e.conversation_id === conv && (e.event === 'created' || e.event === 'converged'));
mark('mixed_request', { tool_calls: mixed.summary.tool_calls.map((c) => c.name), tasks: created.map((e) => e.task_id), assistant: mixed.summary.assistant.slice(0, 300) });
const tasks = [...new Set(created.map((e) => e.task_id))];
let decisionTask = null;
for (const t of tasks) { const v = await inspect(t); if (v.pending_human_decision || v.accepted_spec?.payload?.capabilities?.includes('human.request')) decisionTask = t; }

// Pause: every client disconnects.
desk.close();
mark('all_clients_disconnected');
// While disconnected: the summary Task completes on its own; the decision is answered at the Blaine ingress.
await until(() => jsonl(`${base}.deliveries.jsonl`).some((e) => e.event === 'confirmed' && e.key.startsWith(`${decisionTask}:decision`)), 180000, 'decision card projected while disconnected');
const cardMsg = await (async () => { const c = new V2Client({ port: Number(port), token: stateToken(state), name: 'lw-peek', trace: null }); await c.connect();
  const m = await c.request({ type: 'conversation_messages_list', conversation_id: conv, query: { limit: 200, order: 'desc' } }); c.close();
  return (m.messages ?? []).find((x) => (x.otid ?? '').startsWith('blaine-proj-') && JSON.stringify(x.content).includes('waiting for YOUR decision')); })();
const code = /\/decide ([A-F0-9]{6})/.exec(JSON.stringify(cardMsg.content))[1];
const answer = await handleHumanText({ bindingsPath, conversationId: conv, principal: 'spike-human@phone-ingress', text: `/decide ${code} NO` });
mark('decision_answered_at_blaine_ingress_while_no_letta_client', { code, blaine_status: answer.blaine_status });
for (const t of tasks) await until(async () => ['COMPLETED', 'FAILED', 'CANCELLED'].includes((await inspect(t)).lifecycle), 120000, 'task terminal');
await until(() => tasks.every((t) => jsonl(`${base}.deliveries.jsonl`).some((e) => e.event === 'confirmed' && e.key.startsWith(`${t}:terminal`))), 180000, 'terminal projections while disconnected');
mark('both_tasks_terminal_and_projected_while_disconnected', { states: await Promise.all(tasks.map(async (t) => (await inspect(t)).lifecycle)) });
await sleep(20000); // let projection turns finish with nobody attached

// Resume from another interface: ACP session/load.
const token = readFileSync(`${state}/ws-token`, 'utf8').trim();
const acpEnv = { PATH: process.env.PATH, HOME: process.env.ACP_HOME, LETTA_ACP_BACKEND: 'remote', LETTA_APP_SERVER_URL: `ws://127.0.0.1:${port}`, LETTA_APP_SERVER_TOKEN: token,
  LETTA_AGENT_ID: agentId, LETTA_ACP_STATE_DIR: `${process.env.ACP_HOME}/acp-sessions`, DO_NOT_TRACK: '1', LETTA_CODE_TELEM: '0', DISABLE_AUTOUPDATER: '1', LETTA_DISABLE_MODS: '1' };
const acp = await withAcp({ sdkPath: process.env.ACP_SDK, command: ['node', process.env.ACP_BIN], env: acpEnv, permission: () => 'reject_once' }, async ({ ctx, acp: a, updates }) => {
  await ctx.request(a.methods.agent.session.load, { sessionId: conv, cwd: `${state}/work`, mcpServers: [] });
  const replay = updates.length;
  const replayText = updates.slice(0, replay).map((u) => u.text ?? '').join('\n');
  await ctx.request(a.methods.agent.session.prompt, { sessionId: conv, prompt: [{ type: 'text', text: 'I am back on my laptop IDE. Briefly: what happened while I was away, and given the Birch decision, what should we do next?' }] });
  return { replay, sees_decision_outcome: /finished: COMPLETED/.test(replayText), sees_summary_result: /Acme 99\.95/.test(replayText) || replayText.includes('finished'),
    continuation: updates.slice(replay).filter((u) => u.kind === 'agent_message_chunk').map((u) => u.text ?? '').join('').slice(0, 600),
    continuation_tools: updates.slice(replay).filter((u) => u.kind === 'tool_call').map((u) => u.title) };
});
mark('resumed_via_acp_session_load', acp.result);

// Back to the desktop client.
desk = new Human({ state, port, name: 'lw-desktop-2', approveDelayMs: 1500, approve: () => ({ behavior: 'deny', message: 'no' }) });
await desk.start({ agent_id: agentId, conversation_id: conv, mode: 'strict' });
const back = await desk.say('Back at the desk. One line: where do we stand on the vendor review?');
mark('desktop_returns', { assistant: back.summary.assistant.slice(0, 300) });
const history = brief(await desk.transcript(400));
desk.close();

const binding = { conversation: conv, agent: agentId, project: 'project-vendor-review', tasks,
  deliveries: jsonl(`${base}.deliveries.jsonl`).filter((e) => tasks.some((t) => (e.key ?? '').startsWith(t)) && e.event === 'confirmed').map((e) => ({ key: e.key.replace(/^(task-.{10}).*?:/, '$1…:'), message_id: e.message_id })) };
const result = { timeline, session1: s1, binding_metadata_needed_outside_letta: binding,
  history_summary: history.map((m) => `${m.type}${(m.otid ?? '').startsWith('blaine-proj-') ? '[projection]' : ''}${m.tool ? '(' + m.tool + ')' : ''}: ${m.text.slice(0, 70)}`) };
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result, null, 1).slice(0, 12000));
process.exit(0);
