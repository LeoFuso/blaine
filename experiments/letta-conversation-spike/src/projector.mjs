// Spike projector: Blaine Task events -> the bound Letta conversation, effectively once.
//
// node src/projector.mjs --state S --port P --bindings B.json [--interval-ms 2000]
//   [--crash-after-send] [--no-guard] [--name proj]
//
// Delivery protocol per (task, event):
//   key = task_id:kind:discriminator; client_message_id = "blaine-proj-" + sha(key)
//   1. ledger "attempt" (durable) -> 2. input create_message (deterministic client_message_id)
//   3. confirm ONLY by reading the transcript back (message with that otid), ledger "confirmed".
//   On restart: attempted-but-unconfirmed keys are checked against the transcript before any resend.
// Projection turns carry client_tool_allowlist ["blaine_task_status"]: the reply turn can only read
// Blaine state (the allowlist also filters external tools; [] would leave vLLM an empty tools array).
import { appendFileSync, existsSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { parseArgs } from 'node:util';
import { V2Client, stateToken } from './v2client.mjs';

const { values: opt } = parseArgs({ options: {
  state: { type: 'string' }, port: { type: 'string' }, bindings: { type: 'string' },
  shim: { type: 'string', default: 'http://127.0.0.1:59090' },
  'interval-ms': { type: 'string', default: '2000' },
  'crash-after-send': { type: 'boolean', default: false },
  once: { type: 'boolean', default: false },
  name: { type: 'string', default: 'projector' },
} });
const base = opt.bindings.replace(/\.json$/, '');
const deliveryPath = `${base}.deliveries.jsonl`;
const sha = (s) => createHash('sha256').update(s).digest('hex');
const now = () => new Date().toISOString();
const log = (entry) => appendFileSync(deliveryPath, JSON.stringify({ t: now(), c: opt.name, ...entry }) + '\n');
const readJsonl = (path) => (existsSync(path) ? readFileSync(path, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []);

async function shim(op, body) {
  const response = await fetch(`${opt.shim}/${op}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? `shim ${response.status}`);
  return data;
}

// Tasks bound to conversations come from the controller ledger (ConversationBinding).
function boundTasks() {
  const tasks = new Map();
  for (const e of readJsonl(`${base}.ledger.jsonl`)) {
    if ((e.event === 'created' || e.event === 'converged') && e.task_id && e.conversation_id) tasks.set(e.task_id, e.conversation_id);
  }
  const bindings = existsSync(opt.bindings) ? JSON.parse(readFileSync(opt.bindings, 'utf8')).conversations ?? {} : {};
  return [...tasks].filter(([, c]) => bindings[c]).map(([task, c]) => ({ task, conversation: c, agent: bindings[c].agent_id }));
}

export function decisionCode(taskId, pending, digest) {
  return sha(`${taskId}|${pending.request_id}|${pending.revision}|${digest}`).slice(0, 6).toUpperCase();
}

function events(view) {
  const out = [];
  const pending = view.pending_human_decision;
  if (view.lifecycle === 'WAITING' && pending) {
    const p = pending.payload;
    const digest = view.pending_digest;
    const code = decisionCode(view.task_id, p, digest);
    out.push({ key: `${view.task_id}:decision:${p.revision}:${digest}`, kind: 'decision', text: [
      `[Blaine notification — not written by the user] Task ${view.task_id.slice(0, 13)}… is waiting for YOUR decision.`,
      `Question (exact): ${p.question}`,
      `Allowed answers: ${p.allowed_responses.join(' | ')} · request ${p.request_id} · revision ${p.revision}`,
      `Request digest: ${digest}`,
      `To answer, the user types exactly: /decide ${code} ${p.allowed_responses[0]}  (or ${p.allowed_responses.slice(1).join(' / ')})`,
      'The assistant cannot answer on the user\'s behalf.',
    ].join('\n') });
  }
  if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(view.lifecycle)) {
    const result = view.result?.payload ?? {};
    const completion = view.completion?.payload ?? {};
    out.push({ key: `${view.task_id}:terminal:${view.lifecycle}`, kind: 'terminal', text: [
      ...(view.recorded_decision ? [`Recorded human decision (verified by Blaine): ${view.recorded_decision}`] : []),
      `[Blaine notification — not written by the user] Task ${view.task_id.slice(0, 13)}… finished: ${view.lifecycle}.`,
      `Objective: ${String(view.objective).slice(0, 200)}`,
      `Artifacts: ${Object.keys(result.artifacts ?? view.artifacts ?? {}).join(', ') || 'none'} · concerns: ${(result.concerns ?? []).join('; ') || 'none'}`,
      `Completion evidence: ${JSON.stringify(completion.criteria ?? completion.outcome ?? completion).slice(0, 300)}`,
    ].join('\n') });
  }
  return out;
}

async function transcriptHas(client, conversationId, otid) {
  const listed = await client.request({ type: 'conversation_messages_list', conversation_id: conversationId, query: { limit: 200, order: 'desc' } });
  return (listed.messages ?? []).find((m) => m.otid === otid) ?? null;
}

async function tick(client) {
  const ledger = readJsonl(deliveryPath);
  const confirmed = new Set(ledger.filter((e) => e.event === 'confirmed').map((e) => e.key));
  const attempted = new Set(ledger.filter((e) => e.event === 'attempt').map((e) => e.key));
  for (const { task, conversation, agent } of boundTasks()) {
    let view;
    try {
      view = await shim('inspect', { task_id: task });
      if (view.pending_human_decision) view.pending_digest = (await shim('decision_view', { task_id: task })).digest;
      if (view.lifecycle === 'COMPLETED' && view.artifacts?.response) {
        try { view.recorded_decision = JSON.parse((await shim('artifact', { task_id: task, name: 'response' })).content)?.payload?.value ?? null; } catch { view.recorded_decision = null; }
      }
    } catch (error) { log({ event: 'inspect_failed', task, error: error.message }); continue; }
    for (const ev of events(view)) {
      if (confirmed.has(ev.key)) continue;
      const cmid = 'blaine-proj-' + sha(ev.key).slice(0, 32);
      if (attempted.has(ev.key)) {
        const found = await transcriptHas(client, conversation, cmid);
        if (found) { log({ event: 'confirmed', key: ev.key, cmid, message_id: found.id, via: 'readback-after-attempt' }); confirmed.add(ev.key); continue; }
        log({ event: 'resend', key: ev.key, cmid });
      }
      log({ event: 'attempt', key: ev.key, cmid, conversation, kind: ev.kind });
      attempted.add(ev.key);
      const accepted = await client.request({ type: 'input', runtime: { agent_id: agent, conversation_id: conversation },
        payload: { kind: 'create_message', messages: [{ role: 'user', content: ev.text, client_message_id: cmid }], client_tool_allowlist: ['blaine_task_status'] } },
        { type: 'input_accepted' });
      log({ event: 'input_accepted', key: ev.key, cmid, accepted: accepted.accepted, disposition: accepted.disposition ?? null, error: accepted.error ?? null });
      if (opt['crash-after-send']) { log({ event: 'fault_crash_after_send', key: ev.key }); process.exit(137); }
      // Confirmation is by read-back only; a queued input is not yet in the transcript.
      for (let i = 0; i < 60; i++) {
        const found = await transcriptHas(client, conversation, cmid);
        if (found) { log({ event: 'confirmed', key: ev.key, cmid, message_id: found.id, via: 'readback' }); confirmed.add(ev.key); break; }
        await new Promise((r) => setTimeout(r, 500));
      }
    }
  }
}

async function main() {
  const client = new V2Client({ port: Number(opt.port), token: stateToken(opt.state), name: opt.name, trace: `${opt.state}/logs/${opt.name}-trace.jsonl` });
  await client.connect();
  log({ event: 'connected' });
  for (;;) {
    if (!client.open) throw new Error('socket closed');
    try { await tick(client); } catch (error) { log({ event: 'tick_error', error: error.message }); if (/closed/.test(error.message)) throw error; }
    if (opt.once) break;
    await new Promise((r) => setTimeout(r, Number(opt['interval-ms'])));
  }
  client.close();
}

for (;;) {
  try { await main(); if (opt.once) process.exit(0); } catch (error) { log({ event: 'session_error', error: error.message }); }
  await new Promise((r) => setTimeout(r, 1000));
}
