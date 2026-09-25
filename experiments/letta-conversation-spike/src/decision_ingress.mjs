// Blaine-owned decision ingress (spike form of what the Blaine gateway / ACP bridge
// would do): a human's "/decide CODE VALUE" is intercepted BEFORE Letta and sent
// directly to the Blaine binding with the revision/digest of the card the code names.
// Letta never carries the answer as authority; the model has no respond tool.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';

const sha = (s) => createHash('sha256').update(s).digest('hex');
export const DECIDE = /^\/decide\s+([A-F0-9]{6})\s+(\S+)\s*$/i;

async function shim(op, body) {
  const r = await fetch(`http://127.0.0.1:59090/${op}`, { method: 'POST', body: JSON.stringify(body) });
  return { status: r.status, body: await r.json() };
}

function boundTasks(bindingsPath, conversationId) {
  const ledger = bindingsPath.replace(/\.json$/, '') + '.ledger.jsonl';
  if (!existsSync(ledger)) return [];
  return [...new Set(readFileSync(ledger, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l))
    .filter((e) => (e.event === 'created' || e.event === 'converged') && e.conversation_id === conversationId).map((e) => e.task_id))];
}

// Resolve a card code to the exact request it was shown for (same derivation as the projector).
export async function resolveCode(bindingsPath, conversationId, code) {
  for (const task of boundTasks(bindingsPath, conversationId)) {
    const dv = (await shim('decision_view', { task_id: task })).body;
    if (!dv.pending) continue;
    const p = dv.pending.payload;
    if (sha(`${task}|${p.request_id}|${p.revision}|${dv.digest}`).slice(0, 6).toUpperCase() === code.toUpperCase()) {
      return { task, request_id: p.request_id, revision: p.revision, digest: dv.digest, allowed: p.allowed_responses };
    }
  }
  return null;
}

// Returns null when the text is not a decision command (forward it to Letta as usual).
export async function handleHumanText({ bindingsPath, conversationId, principal, text, override = {} }) {
  const m = DECIDE.exec(text.trim());
  if (!m) return null;
  const card = await resolveCode(bindingsPath, conversationId, m[1]);
  if (!card) return { intercepted: true, accepted: false, reason: 'No open decision card with this code in this conversation' };
  const response = { task_id: card.task, request_id: card.request_id, request_revision: override.revision ?? card.revision,
    request_digest: override.digest ?? card.digest, response_id: 'resp-' + sha(`${principal}|${conversationId}|${Date.now()}`).slice(0, 24),
    value: override.value ?? m[2].toUpperCase() };
  const result = await shim('respond', response);
  return { intercepted: true, principal, card, submitted: response, blaine_status: result.status, blaine: result.body };
}
