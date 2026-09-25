// Scriptable "human" client for the spike: one App Server connection that
// starts/resumes a runtime, sends user messages, and answers approvals by policy.
//
// import { Human } from './human.mjs'
import { randomUUID } from 'node:crypto';
import { V2Client, stateToken, summarizeDeltas } from './v2client.mjs';

export class Human {
  constructor({ state, port, name = 'human', approveDelayMs = 300, approve = () => ({ behavior: 'deny', message: 'Denied by spike human policy' }) }) {
    this.approveDelayMs = approveDelayMs;
    this.client = new V2Client({ port: Number(port), token: stateToken(state), name, trace: `${state}/logs/${name}-trace.jsonl` });
    this.approve = approve;
    this.approvals = [];
  }

  async start(command) {
    await this.client.connect();
    const response = await this.client.request({ type: 'runtime_start', client_info: { name: 'blaine-spike-human' },
      force_device_status: true, wait_for_replay: true, ...command }, { timeoutMs: 120000 });
    if (!response.success) throw new Error(`runtime_start failed: ${response.error}`);
    this.runtime = response.runtime;
    this.client.on('control_request', (frame) => {
      if (frame.conversation_id && frame.conversation_id !== this.runtime.conversation_id) return;
      const decision = this.approve(frame.request);
      this.approvals.push({ at: Date.now(), request_id: frame.request_id, tool: frame.request.tool_name, input: frame.request.input,
        suggestions: frame.request.permission_suggestions, decision });
      if (decision === null) return; // leave pending (e.g. to test another client or a crash)
      const entry = this.approvals.at(-1);
      setTimeout(async () => {
        try {
          const ack = await this.client.request({ type: 'input', runtime: this.runtime,
            payload: { kind: 'approval_response', request_id: frame.request_id, decision } }, { type: 'input_accepted' });
          entry.ack = { accepted: ack.accepted, error: ack.error ?? null };
        } catch (error) { entry.ack = { error: String(error) }; }
      }, this.approveDelayMs);
    });
    return response;
  }

  // Send one user message; resolve at this runtime's next turn_finished.
  async say(text, { payload = {}, clientMessageId = randomUUID(), timeoutMs = 600000, wait = true } = {}) {
    const deltas = [];
    const collect = (f) => { if (f.runtime?.conversation_id === this.runtime.conversation_id) deltas.push(f); };
    this.client.on('frame', collect);
    try {
      const accepted = await this.client.request({ type: 'input', runtime: this.runtime,
        payload: { kind: 'create_message', messages: [{ role: 'user', content: text, client_message_id: clientMessageId }], ...payload } },
        { type: 'input_accepted' });
      if (!wait || !accepted.accepted) return { accepted, clientMessageId, deltas };
      const finished = await this.client.waitFor((f) => f.type === 'turn_finished' && f.runtime?.conversation_id === this.runtime.conversation_id, timeoutMs, 'turn_finished');
      return { accepted, finished, clientMessageId, deltas, summary: summarizeDeltas(deltas) };
    } finally {
      this.client.off('frame', collect);
    }
  }

  async transcript(limit = 200) {
    const listed = await this.client.request({ type: 'conversation_messages_list', conversation_id: this.runtime.conversation_id, query: { limit, order: 'asc' } });
    return listed.messages ?? [];
  }

  close() { this.client.close(); }
}

export function brief(messages) {
  return messages.map((m) => {
    const content = m.content ?? m.reasoning ?? '';
    const text = typeof content === 'string' ? content : Array.isArray(content) ? content.map((c) => c.text ?? '').join('') : JSON.stringify(content);
    return { id: m.id, type: m.message_type, otid: m.otid ?? null,
      tool: m.tool_call?.name ?? m.tool_calls?.[0]?.name ?? null, tool_call_id: m.tool_call_id ?? m.tool_call?.tool_call_id ?? m.tool_calls?.[0]?.tool_call_id ?? null,
      status: m.status ?? null, text: text.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/g, '[reminder]').slice(0, 240) };
  });
}
