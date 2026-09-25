// Minimal ACP client used by the spike: spawns an ACP agent command over stdio
// (letta-acp directly, or through a relay) and records every session/update.
import { spawn } from 'node:child_process';
import { appendFileSync } from 'node:fs';
import { Readable, Writable } from 'node:stream';

export async function withAcp({ sdkPath, command, env, log = () => {}, permission = () => 'allow_once', stderrPath = null }, body) {
  const acp = await import(sdkPath);
  const [bin, ...args] = command;
  const child = spawn(bin, args, { stdio: ['pipe', 'pipe', 'pipe'], env });
  const stderr = [];
  child.stderr.on('data', (d) => { stderr.push(d.toString()); if (stderrPath) appendFileSync(stderrPath, d); });
  const stream = acp.ndJsonStream(Writable.toWeb(child.stdin), Readable.toWeb(child.stdout));
  const updates = [];
  const permissions = [];
  let result;
  try {
    await acp.client({ name: 'blaine-letta-spike-acp-client' })
      .onRequest(acp.methods.client.session.requestPermission, (ctx) => {
        const optionId = permission(ctx.params);
        permissions.push({ title: ctx.params.toolCall?.title, rawInput: ctx.params.toolCall?.rawInput, options: ctx.params.options?.map((o) => o.optionId), chose: optionId });
        return { outcome: { outcome: 'selected', optionId } };
      })
      .onNotification(acp.methods.client.session.update, (ctx) => {
        const u = ctx.params.update;
        const text = u.content?.type === 'text' ? u.content.text : undefined;
        updates.push({ at: Date.now(), session: ctx.params.sessionId, kind: u.sessionUpdate, text: text?.slice(0, 400), title: u.title, status: u.status, toolCallId: u.toolCallId });
        log(u);
      })
      .connectWith(stream, async (ctx) => {
        const init = await ctx.request(acp.methods.agent.initialize, { protocolVersion: acp.PROTOCOL_VERSION, clientCapabilities: {} });
        result = await body({ ctx, acp, init, updates, permissions });
      });
  } finally {
    child.kill();
  }
  return { result, updates, permissions, stderr: stderr.join('').slice(-4000) };
}
