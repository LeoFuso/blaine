// Attach to a conversation, show pending approvals, answer them, wait for the turn.
// node src/approve.mjs STATE PORT AGENT_ID CONVERSATION_ID allow|deny|show [name]
import { V2Client, stateToken, summarizeDeltas } from './v2client.mjs';

const [state, port, agentId, conversationId, action, name = 'approver'] = process.argv.slice(2);
const client = new V2Client({ port: Number(port), token: stateToken(state), name, trace: `${state}/logs/${name}-trace.jsonl` });
await client.connect();
const statuses = [];
const controls = [];
client.on('update_device_status', (f) => statuses.push(f.device_status));
client.on('control_request', (f) => controls.push(f));
const start = await client.request({ type: 'runtime_start', agent_id: agentId, conversation_id: conversationId,
  client_info: { name: 'blaine-spike-approver' }, force_device_status: true, wait_for_replay: true, recover_approvals: true }, { timeoutMs: 60000 });
await new Promise((r) => setTimeout(r, 800));
const pending = statuses.at(-1)?.pending_control_requests ?? [];
const out = { runtime: start.runtime, mode: statuses.at(-1)?.current_permission_mode, pending: pending.map((p) => ({ request_id: p.request_id, tool: p.request.tool_name, input: p.request.input })), controls: controls.map((c) => c.request_id) };
if (action !== 'show' && pending.length) {
  const deltas = [];
  client.on('frame', (f) => { if (f.runtime?.conversation_id === conversationId) deltas.push(f); });
  out.acks = [];
  for (const p of pending) {
    const decision = action === 'allow' ? { behavior: 'allow' } : { behavior: 'deny', message: 'Denied by spike approver' };
    const ack = await client.request({ type: 'input', runtime: start.runtime, payload: { kind: 'approval_response', request_id: p.request_id, decision } }, { type: 'input_accepted' });
    out.acks.push({ request_id: p.request_id, accepted: ack.accepted, error: ack.error ?? null });
  }
  try {
    const fin = await client.waitFor((f) => f.type === 'turn_finished' && f.runtime?.conversation_id === conversationId, 300000, 'turn_finished');
    out.turn = { stop_reason: fin.stop_reason, summary: summarizeDeltas(deltas) };
  } catch (error) { out.turn = { error: String(error) }; }
}
console.log(JSON.stringify(out, null, 1));
client.close();
process.exit(0);
