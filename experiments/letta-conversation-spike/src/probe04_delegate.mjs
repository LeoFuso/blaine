// Probe 04: discussion without a Task, then delegation of one decision Task,
// then a status question. Human approves only blaine_task_create/status.
// node src/probe04_delegate.mjs STATE PORT AGENT_ID BINDINGS OUT
import { readFileSync, writeFileSync } from 'node:fs';
import { Human, brief } from './human.mjs';

const [state, port, agentId, bindingsPath, out] = process.argv.slice(2);
const allowCreate = (req) => (['blaine_task_create', 'blaine_task_status'].includes(req.tool_name)
  ? { behavior: 'allow' } : { behavior: 'deny', message: 'Spike human denies non-Blaine tools' });
const human = new Human({ state, port, name: 'probe04', approve: allowCreate });
const start = await human.start({ agent_id: agentId, create_conversation: { body: {} }, mode: 'strict' });
const runtime = start.runtime;
const bindings = JSON.parse(readFileSync(bindingsPath, 'utf8'));
bindings.conversations[runtime.conversation_id] = { agent_id: agentId, project: 'spike-project' };
writeFileSync(bindingsPath, JSON.stringify(bindings, null, 1));
await new Promise((r) => setTimeout(r, 2500));

const steps = [];
for (const text of [
  'Morning. Context: we are preparing the synthetic Q3 operations report. No action needed yet: name two risks you would watch for in such a report.',
  'Please open a formal Blaine decision for me with exactly this question: "Approve publishing the synthetic Q3 operations report draft?"',
  'What is the current status of that decision Task? Check Blaine, do not guess.',
]) {
  const turn = await human.say(text);
  await new Promise((r) => setTimeout(r, Number(process.env.INTER_TURN_MS ?? 0)));
  steps.push({ user: text, stop_reason: turn.finished?.stop_reason, tool_calls: turn.summary.tool_calls, tool_returns: turn.summary.tool_returns, assistant: turn.summary.assistant.slice(0, 600) });
}
const ledger = readFileSync(bindingsPath.replace(/\.json$/, '') + '.ledger.jsonl', 'utf8').trim().split('\n').map((l) => JSON.parse(l))
  .filter((e) => e.conversation_id === runtime.conversation_id || steps.some((s) => s.tool_calls.some((c) => c.id === e.tool_call_id)));
const result = { runtime, steps, approvals: human.approvals.map((a) => ({ tool: a.tool, input: a.input, suggestions: a.suggestions, decision: a.decision.behavior })),
  ledger, transcript: brief(await human.transcript()) };
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result, null, 1).slice(0, 9000));
human.close();
process.exit(0);
