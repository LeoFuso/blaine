// Minimal Letta App Server protocol-v2 client (letta-code 0.33.1 frames).
// Spike code: one WebSocket, request/response correlation by request_id,
// every frame appended to a JSONL trace for evidence.
import { EventEmitter } from 'node:events';
import { appendFileSync, readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import WebSocket from 'ws';

const TRUNCATE = 4000;

function shrink(value) {
  const text = JSON.stringify(value);
  return text.length <= TRUNCATE ? value : { truncated: true, bytes: text.length, head: text.slice(0, TRUNCATE) };
}

export function stateToken(stateDir) {
  return readFileSync(`${stateDir}/ws-token`, 'utf8').trim();
}

export class V2Client extends EventEmitter {
  constructor({ port, token, name = 'client', trace = null }) {
    super();
    this.url = `ws://127.0.0.1:${port}/ws`;
    this.token = token;
    this.name = name;
    this.trace = trace;
    this.pending = new Map();
    this.frames = [];
    this.setMaxListeners(100);
  }

  log(direction, frame) {
    if (!this.trace) return;
    appendFileSync(this.trace, JSON.stringify({ t: Date.now(), c: this.name, d: direction, f: shrink(frame) }) + '\n');
  }

  connect(timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(this.url, { headers: { Authorization: `Bearer ${this.token}` } });
      const timer = setTimeout(() => reject(new Error('connect timeout')), timeoutMs);
      ws.on('open', () => { clearTimeout(timer); this.ws = ws; this.log('open', {}); resolve(this); });
      ws.on('error', (error) => { clearTimeout(timer); this.emit('socket_error', error); reject(error); });
      ws.on('close', (code) => {
        this.log('close', { code });
        for (const [, p] of this.pending) p.reject(new Error(`socket closed (${code})`));
        this.pending.clear();
        this.emit('closed', code);
      });
      ws.on('message', (data) => {
        let frame;
        try { frame = JSON.parse(data.toString()); } catch { return; }
        this.log('in', frame);
        this.frames.push(frame);
        const waiter = frame.request_id && this.pending.get(frame.request_id);
        if (waiter && (!waiter.type || waiter.type === frame.type)) {
          this.pending.delete(frame.request_id);
          waiter.resolve(frame);
        }
        this.emit('frame', frame);
        if (frame.type) this.emit(frame.type, frame);
      });
    });
  }

  send(frame) {
    this.log('out', frame);
    this.ws.send(JSON.stringify(frame));
  }

  get open() {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  request(frame, { type = `${frame.type}_response`, timeoutMs = 30000 } = {}) {
    // ws.send on a closed socket fails silently; fail fast so callers reconnect.
    if (!this.open) return Promise.reject(new Error('socket closed (not open)'));
    const requestId = frame.request_id ?? `${this.name}-${frame.type}-${randomUUID()}`;
    const full = { ...frame, request_id: requestId };
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(requestId);
        reject(new Error(`timeout waiting for ${type}`));
      }, timeoutMs);
      this.pending.set(requestId, {
        type,
        resolve: (value) => { clearTimeout(timer); resolve(value); },
        reject: (error) => { clearTimeout(timer); reject(error); },
      });
      this.send(full);
    });
  }

  waitFor(predicate, timeoutMs = 120000, label = 'frame') {
    return new Promise((resolve, reject) => {
      const onFrame = (frame) => {
        if (predicate(frame)) { cleanup(); resolve(frame); }
      };
      const onClosed = () => { cleanup(); reject(new Error(`socket closed waiting for ${label}`)); };
      const timer = setTimeout(() => { cleanup(); reject(new Error(`timeout waiting for ${label}`)); }, timeoutMs);
      const cleanup = () => { clearTimeout(timer); this.off('frame', onFrame); this.off('closed', onClosed); };
      this.on('frame', onFrame);
      this.on('closed', onClosed);
    });
  }

  close() {
    try { this.ws?.close(); } catch { /* ignore */ }
  }

  kill() {
    try { this.ws?.terminate(); } catch { /* ignore */ }
  }
}

export function runtimeOf(agentId, conversationId) {
  return { agent_id: agentId, conversation_id: conversationId };
}

// Collect everything a runtime emits until its turn_finished (or timeout).
export async function sendAndWaitTurn(client, runtime, text, { clientMessageId = randomUUID(), payload = {}, timeoutMs = 300000 } = {}) {
  const deltas = [];
  const collect = (frame) => {
    if (frame.runtime?.conversation_id === runtime.conversation_id) deltas.push(frame);
  };
  client.on('frame', collect);
  try {
    const accepted = await client.request({
      type: 'input', runtime,
      payload: { kind: 'create_message', messages: [{ role: 'user', content: text, client_message_id: clientMessageId }], ...payload },
    }, { type: 'input_accepted' });
    if (!accepted.accepted) return { accepted, deltas, finished: null };
    const finished = await client.waitFor((f) => f.type === 'turn_finished' && f.runtime?.conversation_id === runtime.conversation_id, timeoutMs, 'turn_finished');
    return { accepted, deltas, finished, clientMessageId };
  } finally {
    client.off('frame', collect);
  }
}

// Reassemble assistant text / tool calls from stream deltas (message deltas carry Letta messages).
export function summarizeDeltas(deltas) {
  const out = { assistant: '', reasoning: '', tool_calls: [], tool_returns: [], other: {} };
  for (const frame of deltas) {
    if (frame.type !== 'stream_delta') { out.other[frame.type] = (out.other[frame.type] ?? 0) + 1; continue; }
    const d = frame.delta ?? {};
    const mt = d.message_type;
    if (mt === 'assistant_message') out.assistant += typeof d.content === 'string' ? d.content : (d.content ?? []).map((c) => c.text ?? '').join('');
    else if (mt === 'reasoning_message') out.reasoning += d.reasoning ?? '';
    else if (mt === 'tool_call_message' || mt === 'approval_request_message') {
      const calls = d.tool_calls ?? (d.tool_call ? [d.tool_call] : []);
      for (const c of calls) out.tool_calls.push({ mt, id: c.tool_call_id, name: c.name, args: c.arguments });
    } else if (mt === 'tool_return_message') out.tool_returns.push({ id: d.tool_call_id, status: d.status, ret: String(d.tool_return ?? '').slice(0, 300) });
    else out.other[mt ?? d.type ?? 'unknown'] = (out.other[mt ?? d.type ?? 'unknown'] ?? 0) + 1;
  }
  return out;
}
