// Probe 03b: with toolset "none" persisted and blaine_* registered, a turn with no
// allowlist offers exactly the blaine_* tools (tap-verified).
// node src/probe03b_blaine_only.mjs STATE PORT AGENT_ID CONVERSATION_ID
import { readFileSync } from 'node:fs';
import { Human } from './human.mjs';

const [state, port, agentId, conv] = process.argv.slice(2);
const tap = () => readFileSync(`${state}/logs/llm-requests.jsonl`, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const h = new Human({ state, port, name: 'probe03b' });
await h.start({ agent_id: agentId, conversation_id: conv, mode: 'strict' });
const before = tap().length;
const t = await h.say('Which tools can you call now? Names only, comma separated. Do not call any.');
console.log(JSON.stringify({ assistant: t.summary.assistant, offered: tap().slice(before).map((r) => r.tools) }));
h.close();
process.exit(0);
