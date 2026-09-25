// Probe 16: are canary mods (global ~/.letta/mods and agent MemFS mods/) loaded?
// Run once with the spike posture (LETTA_DISABLE_MODS=1) and once without (positive control).
// node src/probe16_mods.mjs STATE PORT AGENT_ID LABEL OUT
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { V2Client, stateToken, sendAndWaitTurn } from './v2client.mjs';

const [state, port, agentId, label, out] = process.argv.slice(2);
const hostile = () => readFileSync(`${state}/work/hostile-requests.jsonl`, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const c = new V2Client({ port: Number(port), token: stateToken(state), name: `mods-${label}`, trace: `${state}/logs/mods-${label}-trace.jsonl` });
await c.connect();
const statuses = [];
c.on('update_device_status', (f) => statuses.push(f.device_status));
const s = await c.request({ type: 'runtime_start', agent_id: agentId, create_conversation: { body: {} }, mode: 'strict', force_device_status: true, wait_for_replay: true }, { timeoutMs: 60000 });
const n0 = hostile().length;
const t = await sendAndWaitTurn(c, s.runtime, `mods probe ${label}`, { timeoutMs: 120000 });
await new Promise((r) => setTimeout(r, 1000));
const offered = hostile().slice(n0).map((r) => r.tools_offered);
const result = { label, stop: t.finished?.stop_reason, mod_commands: statuses.at(-1)?.mod_commands ?? null,
  canary_tools_offered: offered.flat().filter((n) => n?.startsWith('canary_mod_tool')),
  canary_files: ['global', 'memory'].filter((w) => existsSync(`${state}/work/CANARY-mod-${w}`)) };
writeFileSync(out, JSON.stringify(result, null, 1) + '\n');
console.log(JSON.stringify(result));
c.close();
process.exit(0);
