// Probe 15: letta-acp 0.1.11 (--backend remote) against the spike App Server.
// node src/probe15_acp.mjs STATE PORT AGENT_ID LOAD_CONVERSATION BINDINGS OUT
// Env: ACP_SDK (path to @agentclientprotocol/sdk dist/acp.js), ACP_BIN (letta-acp dist/index.js),
//      ACP_HOME (isolated HOME for the adapter), ACP_WRAP (optional JSON command prefix, e.g. a relay)
import { readFileSync, writeFileSync } from 'node:fs';
import { withAcp } from './acp_client.mjs';

const [state, port, agentId, loadConv, bindingsPath, out] = process.argv.slice(2);
const token = readFileSync(`${state}/ws-token`, 'utf8').trim();
const tap = () => readFileSync(`${state}/logs/llm-requests.jsonl`, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const ledger = () => readFileSync(bindingsPath.replace(/\.json$/, '') + '.ledger.jsonl', 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const env = { PATH: process.env.PATH, HOME: process.env.ACP_HOME, LETTA_ACP_BACKEND: 'remote', LETTA_APP_SERVER_URL: `ws://127.0.0.1:${port}`,
  LETTA_APP_SERVER_TOKEN: token, LETTA_AGENT_ID: agentId, LETTA_ACP_STATE_DIR: `${process.env.ACP_HOME}/acp-sessions`,
  DO_NOT_TRACK: '1', LETTA_CODE_TELEM: '0', DISABLE_AUTOUPDATER: '1', LETTA_DISABLE_MODS: '1' };
const wrap = process.env.ACP_WRAP ? JSON.parse(process.env.ACP_WRAP) : [];
const command = [...wrap, 'node', process.env.ACP_BIN];
const base = { sdkPath: process.env.ACP_SDK, command, env, stderrPath: process.env.ACP_STDERR ?? null };
const summarize = (updates) => updates.reduce((acc, u) => { acc[u.kind] = (acc[u.kind] ?? 0) + 1; return acc; }, {});
const text = (updates, kind) => updates.filter((u) => u.kind === kind && u.text).map((u) => u.text).join('');
const result = {};

// A: session/new -> a new Letta conversation; what tools does it expose?
const t0 = tap().length;
const a = await withAcp(base, async ({ ctx, acp, init, updates }) => {
  const s = await ctx.request(acp.methods.agent.session.new, { cwd: `${state}/work`, mcpServers: [] });
  const r = await ctx.request(acp.methods.agent.session.prompt, { sessionId: s.sessionId, prompt: [{ type: 'text', text: 'Reply with the single word READY.' }] });
  return { init: { protocolVersion: init.protocolVersion, loadSession: init.agentCapabilities?.loadSession }, sessionId: s.sessionId, modes: s.modes, stop: r.stopReason };
});
result.A_session_new = { ...a.result, reply: text(a.updates, 'agent_message_chunk').slice(0, 200), updates: summarize(a.updates),
  tools_offered_to_model: tap().slice(t0).map((r) => r.tools), stderr_tail: a.stderr.slice(-800) };

// B+C: session/load an existing Blaine conversation (history replay), then continue it.
const b = await withAcp(base, async ({ ctx, acp, updates }) => {
  const loaded = await ctx.request(acp.methods.agent.session.load, { sessionId: loadConv, cwd: `${state}/work`, mcpServers: [] });
  const replayed = updates.length;
  const replaySummary = summarize(updates);
  const replayUserTexts = updates.filter((u) => u.kind === 'user_message_chunk').map((u) => (u.text ?? '').slice(0, 90));
  const r = await ctx.request(acp.methods.agent.session.prompt, { sessionId: loadConv, prompt: [{ type: 'text', text: 'In one sentence: what did I decide about the H3 release note, and what is its Blaine Task state?' }] });
  return { modes: loaded.modes, replayed, replaySummary, replayUserTexts, stop: r.stopReason };
});
result.B_session_load = { ...b.result, continuation_reply: text(b.updates.slice(b.result?.replayed ?? 0), 'agent_message_chunk').slice(0, 400),
  tool_calls_during_continuation: b.updates.slice(b.result?.replayed ?? 0).filter((u) => u.kind === 'tool_call').map((u) => u.title), stderr_tail: b.stderr.slice(-800) };

// D: create a Blaine Task through ACP; the permission request reaches the ACP client.
const l0 = ledger().length;
const d = await withAcp(base, async ({ ctx, acp }) => {
  await ctx.request(acp.methods.agent.session.load, { sessionId: loadConv, cwd: `${state}/work`, mcpServers: [] });
  const r = await ctx.request(acp.methods.agent.session.prompt, { sessionId: loadConv, prompt: [{ type: 'text', text: 'Please open a formal Blaine decision with exactly this question: "Approve the synthetic ACP handoff checklist?"' }] });
  return { stop: r.stopReason };
});
result.D_task_via_acp = { ...d.result, permissions: d.permissions, controller: ledger().slice(l0).filter((e) => ['tool_call', 'created', 'converged'].includes(e.event)).map((e) => ({ event: e.event, tool: e.tool, task_id: e.task_id })),
  reply: text(d.updates, 'agent_message_chunk').slice(-300) };

// E: a fresh adapter process loads the same session: continuity across adapter restarts.
const e = await withAcp(base, async ({ ctx, acp, updates }) => {
  await ctx.request(acp.methods.agent.session.load, { sessionId: loadConv, cwd: `${state}/work`, mcpServers: [] });
  return { replayed: updates.length, mentionsAcpChecklist: updates.some((u) => (u.text ?? '').includes('ACP handoff checklist')) };
});
result.E_reload = e.result;
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result, null, 1).slice(0, 9000));
process.exit(0);
