// Stand-in for GitNexus's CLI entry, run by Node. The test writes a `CONFIG` object
// (python, fakeTools, manifest) in front of this file.
//
// Upstream edits OpenCode's first existing config (opencode.json, opencode.jsonc,
// config.json) in place with jsonc-parser, so comments survive. This stand-in does the same
// for `setup -c opencode`. Every other call goes to fake_upstream_tools.py.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { modify, applyEdits } = require(path.join(__dirname, '../../../jsonc-parser'));

const args = process.argv.slice(2);

function editExistingOpenCodeConfig() {
  const directory = path.join(os.homedir(), '.config', 'opencode');
  const file = ['opencode.json', 'opencode.jsonc', 'config.json']
    .map((name) => path.join(directory, name))
    .find((candidate) => fs.existsSync(candidate));
  if (!file) return false;
  const text = fs.readFileSync(file, 'utf8');
  const entry = { type: 'local', command: ['npx', '-y', 'gitnexus@latest', 'mcp'] };
  const edits = modify(text, ['mcp', 'gitnexus'], entry, {
    formattingOptions: { insertSpaces: true, tabSize: 2 },
  });
  fs.writeFileSync(file, applyEdits(text, edits));
  return true;
}

if (args.join(' ') === 'setup -c opencode' && editExistingOpenCodeConfig()) {
  console.log('gitnexus set up for opencode');
  process.exit(0);
}
const env = { ...process.env, LLMS_FAKE_MANIFEST: CONFIG.manifest };
const run = spawnSync(CONFIG.python, [CONFIG.fakeTools, 'gitnexus', __filename, ...args], {
  env,
  stdio: 'inherit',
});
process.exit(run.status ?? 1);
