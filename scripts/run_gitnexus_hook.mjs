// Keep upstream hook logic; select the local runtime and per-repository storage.
import { createRequire } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [node, , storageRoot, hook, cli, ...args] = process.argv;
if (!storageRoot || !hook || !cli) {
  throw new Error('The storage root, upstream hook path, and pinned CLI path are required.');
}
delete process.env.GITNEXUS_STORAGE_PATH;
process.env.GITNEXUS_STORAGE_ROOT = storageRoot;
process.env.GITNEXUS_HOOK_CLI_PATH = cli;
process.env.PATH = [path.dirname(node), process.env.PATH ?? ''].join(path.delimiter);

// The upstream PATH probe misses our private installation and suggests @latest.
// Change only its command formatter; the upstream hook still handles the event.
const require = createRequire(import.meta.url);
const resolver = require(path.join(path.dirname(hook), 'resolve-analyze-cmd.cjs'));
if (typeof resolver.formatAnalyzeCommand !== 'function') {
  throw new Error('The installed GitNexus hook has an unsupported command formatter.');
}
resolver.formatAnalyzeCommand = ({ indexOnly = false, embeddings = false } = {}) => {
  const runner = path.join(import.meta.dirname, 'run_gitnexus.mjs');
  const command = [node, runner, cli, 'analyze'];
  if (indexOnly) command.push('--index-only');
  if (embeddings) command.push('--embeddings');
  const quote = process.platform === 'win32'
    ? (value) => `'${value.replaceAll("'", "''")}'`
    : (value) => `'${value.replaceAll("'", "'\\''")}'`;
  const assignment = `GITNEXUS_STORAGE_ROOT=${quote(storageRoot)}`;
  const launch = command.map(quote).join(' ');
  return process.platform === 'win32'
    ? `$env:${assignment}; & ${launch}`
    : `${assignment} ${launch}`;
};
process.argv = [node, hook, ...args];
await import(pathToFileURL(hook).href);
