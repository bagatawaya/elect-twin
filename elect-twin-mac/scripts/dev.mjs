import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
let port = '7100';
for (let i = 0; i < args.length; i += 1) {
  if (args[i] === '--port' && args[i + 1]) port = args[++i];
  else if (args[i].startsWith('--port=')) port = args[i].slice(7);
}
if (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535) {
  console.error('Port must be an integer from 1 to 65535.');
  process.exit(1);
}
const dataDir = resolve(root, '.local-data');
mkdirSync(dataDir, { recursive: true, mode: 0o700 });
const dataPath = process.env.ELECT_TWIN_DATA || resolve(dataDir, 'projects.sqlite3');
const child = spawn('python3', [
  resolve(root, 'twin.py'),
  '--port', port,
  '--data', dataPath,
  '--development-preview'
], { stdio: 'inherit' });
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal));
}
child.on('exit', (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
