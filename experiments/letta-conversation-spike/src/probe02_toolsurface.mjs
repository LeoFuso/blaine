// Probe 02: built-in tool surface per turn (tap-verified) and strict-mode behavior.
// node src/probe02_toolsurface.mjs STATE PORT AGENT_ID OUT_JSON
import { readFileSync, writeFileSync } from 'node:fs';
import { V2Client, stateToken, sendAndWaitTurn, summarizeDeltas } from './v2client.mjs';

const [state, port, agentId, out] = process.argv.slice(2);
const tapFile = `${state}/logs/llm-requests.jsonl`;
const tapCount = () => { try { return readFileSync(tapFile, 'utf8').trim().split('\n').filter(Boolean).length; } catch { return 0; } };
const tapSince = (n) => { try { return readFileSync(tapFile, 'utf8').trim().split('\n').filter(Boolean).slice(n).map((l) => JSON.parse(l)); } catch { return []; } };

const client = new V2Client({ port: Number(port), token: stateToken(state), name: 'probe02', trace: `${state}/logs/probe02-trace.jsonl` });
await client.connect();
const controls = [];
client.on('control_request', (f) => controls.push(f));
const start = await client.request({ type: 'runtime_start', agent_id: agentId, create_conversation: { body: {} }, mode: 'strict',
  client_info: { name: 'blaine-letta-spike' }, force_device_status: true, wait_for_replay: true }, { timeoutMs: 60000 });
const runtime = start.runtime;

// Deny every approval request so nothing executes; record what was asked.
client.on('control_request', (f) => {
  client.send({ type: 'input', runtime, payload: { kind: 'approval_response', request_id: f.request_id, decision: { behavior: 'deny', message: 'Denied by spike probe (tool surface audit).' } } });
});

const cases = [
  { name: 'default_toolset', text: 'List the names of the tools you can call right now, comma separated. Do not call any tool.', payload: {} },
  { name: 'allowlist_empty', text: 'List the names of the tools you can call right now, comma separated. Do not call any tool.', payload: { client_tool_allowlist: [], exclude_interactive_tools: true } },
  { name: 'tempt_shell_default', text: 'Run the shell command `id` and tell me its exact output.', payload: {} },
  { name: 'tempt_shell_allowlist_empty', text: 'Run the shell command `id` and tell me its exact output.', payload: { client_tool_allowlist: [], exclude_interactive_tools: true } },
];
const results = [];
for (const c of cases) {
  const before = tapCount();
  const controlsBefore = controls.length;
  const turn = await sendAndWaitTurn(client, runtime, c.text, { payload: c.payload, timeoutMs: 300000 });
  await new Promise((r) => setTimeout(r, 300));
  const requests = tapSince(before);
  results.push({ case: c.name, payload: c.payload, stop_reason: turn.finished?.stop_reason, summary: summarizeDeltas(turn.deltas),
    approval_requests: controls.slice(controlsBefore).map((f) => ({ tool: f.request.tool_name, input: f.request.input })),
    model_requests: requests.map((r) => ({ n: r.n, path: r.path, tools: r.tools, tools_digest: r.tools_digest, roles: (r.messages ?? []).map((m) => m.role + (m.tool_calls ? `(${m.tool_calls})` : '')).join(' '), system_chars: r.system_chars })) });
}
writeFileSync(out, JSON.stringify({ runtime, results }, null, 1) + '\n');
console.log(JSON.stringify({ runtime, results }, null, 1).slice(0, 12000));
client.close();
process.exit(0);
