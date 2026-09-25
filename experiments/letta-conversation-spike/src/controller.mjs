// Spike Blaine controller: exposes blaine_* external tools to Letta conversations
// and forwards them to the existing Personal Agent binding (via control_shim.py).
//
// node src/controller.mjs --state S --port P --bindings B.json [--identity toolcall|anchor|reconcile]
//   [--delay-after-create-ms N] [--respond-tool] [--write-scope blaine-write] [--name ctl]
//
// Bindings file (ConversationBinding, spike form):
//   {"conversations": {"<conversation_id>": {"agent_id": "...", "project": "..."}}}
// Ledger (append-only JSONL, same directory): tool calls, request identities, Task ids.
import { appendFileSync, existsSync, readFileSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { parseArgs } from 'node:util';
import { V2Client, stateToken } from './v2client.mjs';

const { values: opt } = parseArgs({ options: {
  state: { type: 'string' }, port: { type: 'string' }, bindings: { type: 'string' },
  shim: { type: 'string', default: 'http://127.0.0.1:59090' },
  identity: { type: 'string', default: 'toolcall' },
  'delay-after-create-ms': { type: 'string', default: '0' },
  'respond-tool': { type: 'boolean', default: false },
  'write-scope': { type: 'string', default: '' },
  name: { type: 'string', default: 'controller' },
} });
const ledgerPath = opt.bindings.replace(/\.json$/, '') + '.ledger.jsonl';
const sha = (s) => createHash('sha256').update(s).digest('hex');
const now = () => new Date().toISOString();
const readLedger = () => (existsSync(ledgerPath) ? readFileSync(ledgerPath, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []);
const record = (entry) => appendFileSync(ledgerPath, JSON.stringify({ t: now(), c: opt.name, ...entry }) + '\n');

async function shim(op, body) {
  const response = await fetch(`${opt.shim}/${op}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.error ?? `shim ${response.status}`), { status: response.status, data });
  return data;
}

const TOOLS = {
  blaine_task_create: {
    description: 'Create a durable Blaine Task. Use it when the user asks for work that must be tracked or needs a decision recorded by Blaine. kind "decision": Blaine asks the user a YES/NO question and records the answer. kind "summary": Blaine computes deterministic statistics of the given text. Returns the Task id; the Task runs independently and Blaine reports its result later.',
    parameters: { type: 'object', additionalProperties: false, required: ['kind'], properties: {
      kind: { type: 'string', enum: ['decision', 'summary'] },
      question: { type: 'string', description: 'For kind=decision: the exact YES/NO question to ask the user.' },
      text: { type: 'string', description: 'For kind=summary: the text to analyse.' } } },
  },
  blaine_task_status: {
    description: 'Read the current authoritative state of a Blaine Task by id. Never guess Task state from the conversation; call this instead.',
    parameters: { type: 'object', additionalProperties: false, required: ['task_id'], properties: { task_id: { type: 'string' } } },
  },
  blaine_task_respond: {
    description: 'Submit the user\'s answer to a pending Blaine decision. Only call this with the exact value the user chose.',
    parameters: { type: 'object', additionalProperties: false, required: ['task_id', 'value', 'request_revision', 'request_digest'], properties: {
      task_id: { type: 'string' }, value: { type: 'string', enum: ['YES', 'NO'] },
      request_revision: { type: 'integer' }, request_digest: { type: 'string' } } },
  },
};

function toolGroups() {
  const read = [{ name: 'blaine_task_status', ...TOOLS.blaine_task_status }];
  const write = [{ name: 'blaine_task_create', ...TOOLS.blaine_task_create }];
  if (opt['respond-tool']) write.push({ name: 'blaine_task_respond', ...TOOLS.blaine_task_respond });
  if (opt['write-scope']) return [{ tools: read }, { scope_id: opt['write-scope'], tools: write }];
  return [{ tools: [...read, ...write] }];
}

function loadBindings() {
  if (!existsSync(opt.bindings)) return {};
  return JSON.parse(readFileSync(opt.bindings, 'utf8')).conversations ?? {};
}

// Anchor identity: the latest human-authored user message (projections excluded by otid prefix).
async function anchorOf(client, conversationId) {
  const listed = await client.request({ type: 'conversation_messages_list', conversation_id: conversationId, query: { limit: 100, order: 'desc' } });
  const users = (listed.messages ?? []).filter((m) => m.message_type === 'user_message');
  const human = users.find((m) => !(m.otid ?? '').startsWith('blaine-proj-'));
  const latestIsProjection = users.length > 0 && (users[0].otid ?? '').startsWith('blaine-proj-');
  return human ? { id: human.id, otid: human.otid ?? null, latestIsProjection } : null;
}

function compact(view) {
  const pending = view.pending_human_decision?.payload;
  return { task_id: view.task_id, lifecycle: view.lifecycle, objective: view.objective,
    pending_decision: pending ? { question: pending.question, allowed_responses: pending.allowed_responses, revision: pending.revision } : null,
    result: view.result ? { outcome: view.result.payload?.outcome, artifacts: Object.keys(view.result.payload?.artifacts ?? {}), concerns: view.result.payload?.concerns ?? [] } : null };
}

// Serialize Blaine calls per conversation: the existing binding's create check is
// check-then-act, so concurrent creates must never race on the Blaine side.
const lanes = new Map();
function inLane(conversationId, fn) {
  const next = (lanes.get(conversationId) ?? Promise.resolve()).then(fn, fn);
  lanes.set(conversationId, next.catch(() => {}));
  return next;
}

async function handleCall(client, frame) {
  return inLane(frame.runtime?.conversation_id ?? 'none', () => handleCallInLane(client, frame));
}

async function handleCallInLane(client, frame) {
  const { tool_call_id: toolCallId, tool_name: tool, input, runtime } = frame;
  const conversationId = runtime?.conversation_id;
  record({ event: 'tool_call', tool_call_id: toolCallId, tool, conversation_id: conversationId, input });
  const bindings = loadBindings();
  if (!bindings[conversationId]) throw new Error('Conversation is not bound to a Blaine project');
  if (tool === 'blaine_task_create') {
    const argsKey = sha(JSON.stringify([input.kind, String(input.question ?? input.text ?? '').trim().replace(/\s+/g, ' ')]));
    if (opt.identity === 'reconcile') {
      // Letta turns an interrupted call into a stale denial and the model re-issues it,
      // possibly under a new user message. Converge on an open Task with identical
      // arguments in this conversation instead of creating a second one.
      const prior = readLedger().filter((e) => e.event === 'created' && e.conversation_id === conversationId && e.args_key === argsKey);
      for (const entry of prior.reverse()) {
        const view = await shim('inspect', { task_id: entry.task_id });
        if (!['COMPLETED', 'FAILED', 'CANCELLED'].includes(view.lifecycle)) {
          record({ event: 'converged', tool_call_id: toolCallId, request_id: entry.request_id, task_id: entry.task_id, conversation_id: conversationId, rule: 'open-identical-args', args_key: argsKey });
          return { note: 'This exact request is already an open Blaine Task (an earlier call was interrupted); no new Task was created.', ...compact(view) };
        }
      }
    }
    let requestId;
    if (opt.identity === 'anchor' || opt.identity === 'reconcile') {
      const anchor = await anchorOf(client, conversationId);
      if (!anchor) throw new Error('No human message anchors this request');
      // Recursion guard: a Blaine notification can never cause Task creation.
      if (anchor.latestIsProjection) throw new Error('Blaine Tasks are created only in direct response to a user message, not to a Blaine notification');
      // Arguments are part of the identity: parallel calls in one turn are distinct requests,
      // and an identical re-issue under the same human message converges.
      requestId = 'lc-' + sha(`${conversationId}|${anchor.id}|${tool}|${argsKey}`).slice(0, 40);
      record({ event: 'identity', tool_call_id: toolCallId, mode: 'anchor', anchor, request_id: requestId });
    } else {
      requestId = 'lc-' + sha(`${conversationId}|${toolCallId}`).slice(0, 40);
      record({ event: 'identity', tool_call_id: toolCallId, mode: 'toolcall', request_id: requestId });
    }
    let receipt;
    try {
      receipt = input.kind === 'decision'
        ? await shim('create_decision', { request_id: requestId, question: String(input.question ?? '').slice(0, 512) })
        : await shim('create_summarize', { request_id: requestId, text: String(input.text ?? '').slice(0, 1024) });
    } catch (error) {
      if (opt.identity !== 'toolcall' && /different input/.test(error.message)) {
        // Same human request re-issued with different wording: converge on the existing Task.
        const taskId = 'task-' + sha(requestId);
        const view = await shim('inspect', { task_id: taskId });
        record({ event: 'converged', tool_call_id: toolCallId, request_id: requestId, task_id: taskId });
        return { note: 'A Blaine Task already exists for this request; no new Task was created.', ...compact(view) };
      }
      throw error;
    }
    record({ event: 'created', tool_call_id: toolCallId, request_id: requestId, task_id: receipt.task_id, submission: receipt.submission, conversation_id: conversationId, args_key: argsKey });
    const delay = Number(opt['delay-after-create-ms']);
    if (delay > 0) {
      record({ event: 'fault_delay', tool_call_id: toolCallId, ms: delay });
      await new Promise((r) => setTimeout(r, delay));
    }
    return { task_id: receipt.task_id, submission: receipt.submission, note: 'Submitted to Blaine. This receipt is not completion; Blaine will post the result to this conversation.' };
  }
  if (tool === 'blaine_task_status') {
    return compact(await shim('inspect', { task_id: String(input.task_id) }));
  }
  if (tool === 'blaine_task_respond') {
    const view = await shim('inspect', { task_id: String(input.task_id) });
    const pending = view.pending_human_decision?.payload;
    if (!pending) throw new Error('No pending decision for this Task');
    const response = await shim('respond', { task_id: view.task_id, request_id: pending.request_id,
      request_revision: input.request_revision, request_digest: input.request_digest,
      response_id: 'resp-' + sha(`${conversationId}|${toolCallId}`).slice(0, 32), value: input.value });
    record({ event: 'responded_via_tool', tool_call_id: toolCallId, task_id: view.task_id, value: input.value, receipt: response });
    return { receipt: response, note: 'Submitted; Blaine validates and records the decision.' };
  }
  throw new Error(`Unknown Blaine tool ${tool}`);
}

let registered = new Set();
async function register(client) {
  const bindings = loadBindings();
  const runtimes = Object.entries(bindings).map(([conversation_id, b]) => ({ agent_id: b.agent_id, conversation_id }));
  // Letta silently drops an update with an empty runtime list (no response frame).
  if (runtimes.length === 0) { record({ event: 'registered', runtimes: 0, skipped: true }); return; }
  const response = await client.request({ type: 'runtime_external_tools_update', updates: [{ runtimes, external_tools: toolGroups() }] });
  registered = new Set(runtimes.map((r) => r.conversation_id));
  record({ event: 'registered', runtimes: runtimes.length, success: response.success, error: response.error ?? null });
}

async function session() {
  const client = new V2Client({ port: Number(opt.port), token: stateToken(opt.state), name: opt.name, trace: `${opt.state}/logs/${opt.name}-trace.jsonl` });
  await client.connect();
  record({ event: 'connected' });
  client.on('external_tool_call_request', async (frame) => {
    let reply;
    try {
      const result = await handleCall(client, frame);
      reply = { type: 'external_tool_call_response', request_id: frame.request_id, result: { content: [{ type: 'text', text: JSON.stringify(result) }] } };
    } catch (error) {
      record({ event: 'tool_error', tool_call_id: frame.tool_call_id, error: error.message });
      reply = { type: 'external_tool_call_response', request_id: frame.request_id, result: { content: [{ type: 'text', text: `Blaine error: ${error.message}` }], is_error: true } };
    }
    try { client.send(reply); record({ event: 'replied', tool_call_id: frame.tool_call_id, is_error: reply.result.is_error === true }); }
    catch (error) { record({ event: 'reply_failed', tool_call_id: frame.tool_call_id, error: error.message }); }
  });
  await register(client);
  let mtime = existsSync(opt.bindings) ? statSync(opt.bindings).mtimeMs : 0;
  const watch = setInterval(async () => {
    const current = existsSync(opt.bindings) ? statSync(opt.bindings).mtimeMs : 0;
    if (current !== mtime) { mtime = current; try { await register(client); } catch (error) { record({ event: 'register_failed', error: error.message }); } }
  }, 1000);
  await new Promise((resolve) => client.once('closed', resolve));
  clearInterval(watch);
  record({ event: 'disconnected' });
}

for (;;) {
  try { await session(); } catch (error) { record({ event: 'session_error', error: error.message }); }
  await new Promise((r) => setTimeout(r, 1000));
}
