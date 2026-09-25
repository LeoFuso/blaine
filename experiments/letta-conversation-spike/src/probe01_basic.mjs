// Probe 01: agent + conversation in local mode, one plain turn, device status.
// node src/probe01_basic.mjs STATE PORT OUT_JSON
import { writeFileSync } from 'node:fs';
import { V2Client, stateToken, runtimeOf, sendAndWaitTurn, summarizeDeltas } from './v2client.mjs';

const [state, port, out] = process.argv.slice(2);
const MODEL = 'openai-compatible/nvidia/Qwen3.8-27B-NVFP4';
const SYSTEM = [
  'You are the Blaine Personal Agent (spike). You help the user think and you delegate durable work to Blaine.',
  'You have no filesystem, shell or web access. Do not claim to have performed actions you cannot perform.',
  'Answer briefly.',
].join('\n');

const client = new V2Client({ port: Number(port), token: stateToken(state), name: 'probe01', trace: `${state}/logs/probe01-trace.jsonl` });
await client.connect();
const statusFrames = [];
client.on('update_device_status', (f) => statusFrames.push(f));
const start = await client.request({
  type: 'runtime_start',
  create_agent: { body: { name: 'blaine-spike-pa', model: MODEL, system: SYSTEM }, pin_global: false },
  create_conversation: { body: {} },
  mode: 'strict',
  client_info: { name: 'blaine-letta-spike', title: 'Blaine spike probe' },
  force_device_status: true,
  wait_for_replay: true,
}, { timeoutMs: 120000 });
const runtime = start.runtime;
await new Promise((r) => setTimeout(r, 500));
const device = statusFrames.at(-1)?.device_status ?? null;
const turn = await sendAndWaitTurn(client, runtime, 'In one sentence: what is a durable task?', { payload: { client_tool_allowlist: [], exclude_interactive_tools: true } });
const result = {
  runtime_start: { success: start.success, created: start.created, error: start.error ?? null, runtime,
    agent: start.agent && { id: start.agent.id, name: start.agent.name, model: start.agent.model ?? start.agent.llm_config?.model, tools: (start.agent.tools ?? []).map((t) => t.name ?? t), tags: start.agent.tags },
    conversation: start.conversation },
  device_status: device && { mode: device.current_permission_mode, toolset: device.current_toolset, toolset_pref: device.current_toolset_preference,
    loaded_tools: device.current_loaded_tools, skills: (device.current_available_skills ?? []).map((s) => `${s.source}:${s.name}`),
    memory_directory: device.memory_directory, version: device.letta_code_version, experiments: device.experiments?.map((e) => `${e.id}=${e.enabled}`),
    supported_commands: device.supported_commands, mod_commands: device.mod_commands ?? null, reflection: device.reflection_settings },
  turn: { accepted: turn.accepted, finished: turn.finished && { stop_reason: turn.finished.stop_reason, usage: turn.finished.usage, error: turn.finished.error ?? null }, summary: summarizeDeltas(turn.deltas) },
};
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result, null, 1).slice(0, 6000));
client.close();
process.exit(0);
