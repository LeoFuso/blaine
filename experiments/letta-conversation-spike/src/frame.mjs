// Exploration helper: node src/frame.mjs STATE PORT '<frame json>' [linger_ms] [response_type]
// Sends one frame, prints the correlated response and every other frame seen while lingering.
import { V2Client, stateToken } from './v2client.mjs';

const [state, port, raw, linger = '1500', responseType] = process.argv.slice(2);
const client = new V2Client({ port: Number(port), token: stateToken(state), name: 'frame', trace: `${state}/logs/frame-trace.jsonl` });
await client.connect();
const frame = JSON.parse(raw);
const seen = [];
client.on('frame', (f) => seen.push(f));
let response = null;
try {
  response = await client.request(frame, responseType ? { type: responseType, timeoutMs: 60000 } : { timeoutMs: 60000 });
} catch (error) {
  response = { error: String(error) };
}
await new Promise((r) => setTimeout(r, Number(linger)));
console.log(JSON.stringify({ response, other: seen.filter((f) => f !== response).map((f) => ({ type: f.type, keys: Object.keys(f) })) }, null, 1));
client.close();
process.exit(0);
