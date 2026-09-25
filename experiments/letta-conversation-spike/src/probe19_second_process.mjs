// Probe 19: a second Letta process (headless `letta -p`, as a channel process would be)
// writes to a conversation the App Server holds loaded. Does state stay consistent?
// node src/probe19_second_process.mjs STATE PORT AGENT_ID OUT
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { V2Client, stateToken, sendAndWaitTurn } from './v2client.mjs';

const [state, port, agentId, out] = process.argv.slice(2);
const HARNESS = new URL('../harness/', import.meta.url).pathname;
const integrity = (conv) => JSON.parse(execFileSync('python3', [`${HARNESS}integrity.py`, state, conv]).toString().trim());
const c = new V2Client({ port: Number(port), token: stateToken(state), name: 'p19', trace: `${state}/logs/p19-trace.jsonl` });
await c.connect();
const s = await c.request({ type: 'runtime_start', agent_id: agentId, create_conversation: { body: {} }, mode: 'strict', wait_for_replay: true }, { timeoutMs: 60000 });
const conv = s.runtime.conversation_id;
await c.request({ type: 'update_toolset', runtime: s.runtime, toolset_preference: 'none' });
for (let i = 0; i < 3; i++) await sendAndWaitTurn(c, s.runtime, `app server turn ${i}`, { timeoutMs: 60000 });
const before = integrity(conv);
// Second process: headless letta against the same local backend state, same conversation.
let headless;
try {
  headless = execFileSync('bash', [`${HARNESS}letta_sandbox.sh`, state, '-p', 'headless second-process turn', '--conversation', conv, '--backend', 'local', '--output-format', 'json'],
    { env: process.env, timeout: 120000 }).toString().slice(-600);
} catch (error) { headless = `error: ${String(error.stderr ?? error).slice(-600)}`; }
const afterHeadless = integrity(conv);
const viewAfterHeadless = await c.request({ type: 'conversation_messages_list', conversation_id: conv, query: { limit: 200, order: 'asc' } });
// App Server appends again with its (possibly stale) in-memory state.
for (let i = 3; i < 5; i++) await sendAndWaitTurn(c, s.runtime, `app server turn ${i}`, { timeoutMs: 60000 });
const after = integrity(conv);
const view = await c.request({ type: 'conversation_messages_list', conversation_id: conv, query: { limit: 200, order: 'asc' } });
const result = { conversation: conv, headless_tail: headless,
  before: { messages: before.messages, in_context: before.in_context },
  after_headless: { messages: afterHeadless.messages, in_context: afterHeadless.in_context, dup_ids: afterHeadless.duplicate_message_ids, app_server_list: viewAfterHeadless.messages?.length },
  after_more_app_server_turns: { messages: after.messages, in_context: after.in_context, dup_ids: after.duplicate_message_ids, missing: after.in_context_missing_from_transcript, unparseable: after.unparseable_lines.length,
    app_server_list: view.messages?.length, headless_message_visible_to_app_server: (view.messages ?? []).some((m) => JSON.stringify(m.content ?? '').includes('headless second-process turn')) } };
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result, null, 1));
c.close();
process.exit(0);
