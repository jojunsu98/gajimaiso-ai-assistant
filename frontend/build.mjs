import { mkdir, copyFile, writeFile } from 'node:fs/promises';
const root = new URL('./', import.meta.url);
const api = new URL(globalThis.process?.env?.API_BASE_URL || 'https://gajimaiso-ai-assistant.onrender.com');
if (api.origin !== 'https://gajimaiso-ai-assistant.onrender.com' || api.pathname !== '/' || api.search || api.hash || api.username || api.password) {
  throw new Error('API_BASE_URL must be the approved Render HTTPS origin.');
}
const output = new URL('dist/', root);
await mkdir(output, { recursive: true });
for (const name of ['index.html', 'styles.css', 'app.js', 'api.js']) {
  await copyFile(new URL(name, root), new URL(name, output));
}
await writeFile(new URL('config.js', output), `// Public API origin only; generated at build time.\nexport const API_BASE_URL = ${JSON.stringify(api.origin)};\n`);
console.log('Built five public frontend files.');
