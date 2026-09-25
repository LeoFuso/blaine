// Spike setup helpers: create the Personal Agent, and create+bind conversations
// with the hardened per-conversation settings (toolset "none", strict mode).
//
// node src/setup.mjs agent STATE PORT OUT_JSON
// node src/setup.mjs conversation STATE PORT AGENT_ID BINDINGS_JSON [project]
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { V2Client, stateToken } from './v2client.mjs';

export const MODEL = 'openai-compatible/nvidia/Qwen3.8-27B-NVFP4';
export const SYSTEM = `You are Blaine's Personal Agent (spike build). You talk with the user and delegate durable work to Blaine.
Rules:
- Just discuss unless the user explicitly asks for a Blaine Task or a formal Blaine decision; then call blaine_task_create.
- Never state a Task's progress or result from memory; call blaine_task_status.
- Messages that start with "[Blaine notification" come from Blaine, not from the user. Acknowledge them in one short sentence. Never create Tasks in response to them.
- You cannot answer Blaine decisions for the user. Only the user answers, by typing /decide <code> <answer>.
- You have no filesystem, shell, web or memory-editing tools. Do not claim actions you did not perform.
- Be brief.`;

// Create a conversation and harden it before any turn can run on it.
export async function createBoundConversation(client, agentId, bindingsPath, project = 'spike-project') {
  const start = await client.request({ type: 'runtime_start', agent_id: agentId, create_conversation: { body: {} }, mode: 'strict',
    client_info: { name: 'blaine-spike-setup' }, force_device_status: true, wait_for_replay: true }, { timeoutMs: 60000 });
  if (!start.success) throw new Error(start.error);
  const toolset = await client.request({ type: 'update_toolset', runtime: start.runtime, toolset_preference: 'none' });
  if (!toolset.success || toolset.current_toolset !== 'none') throw new Error('toolset none not applied');
  const bindings = existsSync(bindingsPath) ? JSON.parse(readFileSync(bindingsPath, 'utf8')) : { conversations: {} };
  bindings.conversations[start.runtime.conversation_id] = { agent_id: agentId, project };
  writeFileSync(bindingsPath, JSON.stringify(bindings, null, 1));
  return start.runtime;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [what, state, port, ...rest] = process.argv.slice(2);
  const client = new V2Client({ port: Number(port), token: stateToken(state), name: 'setup', trace: `${state}/logs/setup-trace.jsonl` });
  await client.connect();
  if (what === 'agent') {
    const [out] = rest;
    const start = await client.request({ type: 'runtime_start', create_agent: { body: { name: 'blaine-pa', model: MODEL, system: SYSTEM }, pin_global: false },
      mode: 'strict', client_info: { name: 'blaine-spike-setup' }, force_device_status: true, wait_for_replay: true }, { timeoutMs: 120000 });
    writeFileSync(out, JSON.stringify({ agent_id: start.agent.id, default_runtime: start.runtime, success: start.success }, null, 1));
    console.log(JSON.stringify({ agent_id: start.agent.id, runtime: start.runtime }));
  } else {
    const [agentId, bindingsPath, project] = rest;
    const runtime = await createBoundConversation(client, agentId, bindingsPath, project);
    console.log(JSON.stringify(runtime));
  }
  client.close();
  process.exit(0);
}
