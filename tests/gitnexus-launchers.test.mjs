import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { pathToFileURL } from 'node:url';
import { quotePowerShell } from '../scripts/quote_powershell.mjs';

const root = path.resolve(import.meta.dirname, '..');
const runner = path.join(root, 'scripts/run_gitnexus.mjs');
const hookRunner = path.join(root, 'scripts/run_gitnexus_hook.mjs');
const gitnexus = path.join(root, '.tools/agent-tools/npm/node_modules/gitnexus');
const upstreamHook = path.join(gitnexus, 'hooks/claude/gitnexus-hook.cjs');

function fixture(t) {
  const directory = mkdtempSync(path.join(os.tmpdir(), "gitnexus launcher's "));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const cli = path.join(directory, 'pinned cli.cjs');
  writeFileSync(cli, `console.log(JSON.stringify({
    args: process.argv.slice(2),
    storageRoot: process.env.GITNEXUS_STORAGE_ROOT,
    storagePath: process.env.GITNEXUS_STORAGE_PATH,
    bufferPool: process.env.GITNEXUS_LBUG_BUFFER_POOL_SIZE,
  }));`);
  const env = { ...process.env, GITNEXUS_STORAGE_PATH: path.join(directory, 'wrong index') };
  delete env.GITNEXUS_STORAGE_ROOT;
  delete env.GITNEXUS_LBUG_BUFFER_POOL_SIZE;
  return { directory, cli, env };
}

function output(result) {
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return JSON.parse(result.stdout);
}

function executeReminder(command, env) {
  assert.doesNotMatch(command, /pnpm|@latest|\bdlx\b|\bnpx\b/);
  const shell = process.platform === 'win32'
    ? path.join(process.env.SystemRoot, 'System32/WindowsPowerShell/v1.0/powershell.exe')
    : '/bin/sh';
  const args = process.platform === 'win32'
    ? ['-NoProfile', '-NonInteractive', '-Command', command]
    : ['-c', command];
  return output(spawnSync(shell, args, {
    env, encoding: 'utf8', windowsHide: true, timeout: 15000,
  }));
}

test('stale reminder executes the pinned CLI with quoted paths and required flags', (t) => {
  const { directory, cli, env } = fixture(t);
  const storageRoot = path.join(directory, 'managed indexes');
  const hooks = path.join(directory, 'hooks');
  mkdirSync(hooks);
  writeFileSync(path.join(hooks, 'resolve-analyze-cmd.cjs'),
    "exports.formatAnalyzeCommand = () => 'pnpm dlx gitnexus@latest analyze';");
  const hook = path.join(hooks, 'hook.cjs');
  writeFileSync(hook, `const {formatAnalyzeCommand} = require('./resolve-analyze-cmd.cjs');
    const options = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
    console.log(JSON.stringify({command: formatAnalyzeCommand(options)}));`);

  for (const embeddings of [false, true]) {
    const { command } = output(spawnSync(process.execPath,
      [hookRunner, storageRoot, hook, cli], {
        env, encoding: 'utf8', input: JSON.stringify({ indexOnly: true, embeddings }),
      }));
    const result = executeReminder(command, env);
    assert.deepEqual(result.args, ['analyze', '--index-only', ...(embeddings ? ['--embeddings'] : [])]);
    assert.equal(result.storageRoot, storageRoot);
    assert.equal(result.storagePath, undefined);
    assert.equal(result.bufferPool, String(4 * 1024 ** 3));
  }
});

test('installed upstream hook emits an executable reminder only for a stale successful mutation', {
  // check sets LLMS_REQUIRE_PINNED_TOOLS so a missing install fails instead of skipping.
  skip: !existsSync(upstreamHook) && !process.env.LLMS_REQUIRE_PINNED_TOOLS
    && 'Install the pinned GitNexus to check its real hook.',
}, async (t) => {
  const { directory, cli, env } = fixture(t);
  const repo = path.join(directory, 'repo');
  mkdirSync(repo);
  const git = (...args) => {
    const result = spawnSync('git', ['-C', repo, ...args], {
      env, encoding: 'utf8', windowsHide: true, timeout: 15000,
    });
    assert.equal(result.status, 0, result.stderr || result.error?.message);
    return result.stdout.trim();
  };
  git('init', '--quiet');
  writeFileSync(path.join(repo, 'fixture.txt'), 'fixture\n');
  git('add', 'fixture.txt');
  git('-c', 'user.name=LauncherTest', '-c', 'user.email=launcher@example.invalid',
    '-c', 'commit.gpgsign=false', '-c', `core.hooksPath=${directory}`,
    'commit', '--quiet', '-m', 'fixture');
  const commit = git('rev-parse', 'HEAD');
  const storageRoot = path.join(directory, 'indexes');
  const { storagePathFromRoot } = await import(pathToFileURL(
    path.join(gitnexus, 'dist/storage/storage-resolver.js'),
  ).href);
  const storagePath = storagePathFromRoot(storageRoot, repo);
  mkdirSync(storagePath, { recursive: true });
  const metadata = { repoPath: repo, storagePath, lastCommit: '0'.repeat(40), stats: { embeddings: 1 } };
  const saveMetadata = () => writeFileSync(path.join(storagePath, 'gitnexus.json'), JSON.stringify(metadata));
  saveMetadata();
  env.GITNEXUS_HOME = path.join(directory, 'home');
  mkdirSync(env.GITNEXUS_HOME);
  writeFileSync(path.join(env.GITNEXUS_HOME, 'registry.json'),
    JSON.stringify([{ name: 'fixture', path: repo, storagePath }]));
  const invoke = (exitCode) => spawnSync(process.execPath,
    [hookRunner, storageRoot, upstreamHook, cli], {
      env, encoding: 'utf8', timeout: 15000,
      input: JSON.stringify({ hook_event_name: 'PostToolUse', tool_name: 'Bash',
        tool_input: { command: 'git commit' }, tool_output: { exit_code: exitCode }, cwd: repo }),
    });

  const { additionalContext } = output(invoke(0)).hookSpecificOutput;
  const match = additionalContext.match(/Run `([^`]+)` to update the knowledge graph\./);
  assert.ok(match, additionalContext);
  const result = executeReminder(match[1], env);
  assert.deepEqual(result.args, ['analyze', '--index-only', '--embeddings']);
  assert.equal(result.storageRoot, storageRoot);
  assert.equal(result.storagePath, undefined);

  const failedMutation = invoke(1);
  assert.equal(failedMutation.status, 0, failedMutation.stderr);
  assert.equal(failedMutation.stdout.trim(), '');
  metadata.lastCommit = commit;
  saveMetadata();
  const currentIndex = invoke(0);
  assert.equal(currentIndex.status, 0, currentIndex.stderr);
  assert.equal(currentIndex.stdout.trim(), '');
});

test('CLI launcher preserves an explicit storage root and forwards the exit code', (t) => {
  const { directory, cli, env } = fixture(t);
  env.GITNEXUS_STORAGE_ROOT = path.join(directory, 'custom indexes');
  env.GITNEXUS_LBUG_BUFFER_POOL_SIZE = '0';
  const result = output(spawnSync(process.execPath, [runner, cli, 'status'], {
    env, encoding: 'utf8',
  }));
  assert.equal(result.storageRoot, env.GITNEXUS_STORAGE_ROOT);
  assert.equal(result.storagePath, undefined);
  assert.equal(result.bufferPool, '0');
  assert.deepEqual(result.args, ['status']);

  delete env.GITNEXUS_LBUG_BUFFER_POOL_SIZE;
  const server = output(spawnSync(process.execPath, [runner, cli, 'mcp'], {
    env, encoding: 'utf8',
  }));
  assert.equal(server.bufferPool, undefined);

  writeFileSync(cli, 'process.exitCode = 7;');
  assert.equal(spawnSync(process.execPath, [runner, cli], { env }).status, 7);
});

// The PowerShell the setup installs (`task deps:dev-tools`), or any pwsh on PATH, if it runs.
function findPowerShell() {
  const installs = path.join(root, '.tools/lint-mise/data/installs/powershell');
  const names = process.platform === 'win32' ? ['pwsh.exe'] : ['pwsh'];
  const candidates = existsSync(installs)
    ? readdirSync(installs).flatMap((version) => names.map((name) => path.join(installs, version, name)))
    : [];
  return [...candidates.filter((candidate) => existsSync(candidate)), 'pwsh'].find((candidate) => (
    spawnSync(candidate, ['-NoProfile', '-NonInteractive', '-Command', 'exit 0']).status === 0
  ));
}

const parseHeader = `
$errors = $null
$tree = [System.Management.Automation.Language.Parser]::ParseInput($env:LLMS_TEST_SCRIPT, [ref] $null, [ref] $errors)
if ($errors.Count -gt 0) { [Console]::Error.WriteLine($errors[0].Message); exit 1 }
`;
// Prints the value of each word on the script's first command line, as PowerShell reads it.
const parseWords = `${parseHeader}
$isCommand = { param($node) $node -is [System.Management.Automation.Language.CommandAst] }
ConvertTo-Json -Compress @($tree.Find($isCommand, $true).CommandElements | ForEach-Object { $_.Value })`;
// Prints every quoted string in the script, including the value assigned to the variable.
const allStringWords = `${parseHeader}
$isString = { param($node) $node -is [System.Management.Automation.Language.StringConstantExpressionAst] }
ConvertTo-Json -Compress @($tree.FindAll($isString, $true) | ForEach-Object { $_.Value })`;

const quoteCharacters = ["'", '\u2018', '\u2019', '\u201a', '\u201b'];

test('PowerShell quoting doubles every single-quote character', () => {
  for (const quote of quoteCharacters) {
    assert.equal(quotePowerShell(`a${quote}b`), `'a${quote}${quote}b'`);
  }
  assert.equal(quotePowerShell("C:/Users/O\u2019Brien/My 'Repos'/llms"),
    "'C:/Users/O\u2019\u2019Brien/My ''Repos''/llms'");
});

test('PowerShell reads back every single-quote character quoted for it', (t) => {
  const pwsh = findPowerShell();
  if (!pwsh) {
    assert.ok(!process.env.LLMS_REQUIRE_PINNED_TOOLS, 'PowerShell is missing; run `task deps:dev-tools`.');
    t.skip('PowerShell is not installed; run `task deps:dev-tools` to check this.');
    return;
  }
  for (const quote of quoteCharacters) {
    const value = `a${quote}b ${quote}${quote} c${quote}`;
    const parsed = spawnSync(pwsh, ['-NoProfile', '-NonInteractive', '-EncodedCommand',
      Buffer.from(parseWords, 'utf16le').toString('base64')], {
      env: { ...process.env, LLMS_TEST_SCRIPT: `& ${quotePowerShell(value)}` },
      encoding: 'utf8', timeout: 60000,
    });
    assert.equal(parsed.status, 0, parsed.stderr);
    assert.deepEqual(JSON.parse(parsed.stdout), [value]);
  }
});

test('Windows stale reminder quotes a U+2019 path so PowerShell reads back the exact paths', (t) => {
  const { directory, env } = fixture(t);
  const hooks = path.join(directory, 'hooks');
  mkdirSync(hooks);
  writeFileSync(path.join(hooks, 'resolve-analyze-cmd.cjs'),
    "exports.formatAnalyzeCommand = () => 'pnpm dlx gitnexus@latest analyze';");
  const hook = path.join(hooks, 'hook.cjs');
  writeFileSync(hook, `const {formatAnalyzeCommand} = require('./resolve-analyze-cmd.cjs');
    console.log(JSON.stringify({command: formatAnalyzeCommand({indexOnly: true})}));`);
  // The runner picks its quoting from process.platform when it builds the command.
  const preload = path.join(directory, 'pretend-windows.mjs');
  writeFileSync(preload, "Object.defineProperty(process, 'platform', { value: 'win32' });");
  const storageRoot = "C:/Users/O\u2019Brien/My 'Repos'/a\u2018b\u201ac\u201bd/indexes";
  const cli = 'C:/Program Files/Tools/gitnexus/dist/cli/index.js';

  const { command } = output(spawnSync(process.execPath,
    ['--import', pathToFileURL(preload).href, hookRunner, storageRoot, hook, cli], { env, encoding: 'utf8' }));
  const words = [process.execPath, path.join(root, 'scripts/run_gitnexus.mjs'), cli, 'analyze', '--index-only'];
  // Written out by hand, not with quotePowerShell, so a fault there cannot hide itself.
  const quotedRoot = "'C:/Users/O\u2019\u2019Brien/My ''Repos''/a\u2018\u2018b\u201a\u201ac\u201b\u201bd/indexes'";
  assert.equal(command,
    `$env:GITNEXUS_STORAGE_ROOT=${quotedRoot}; & ${words.map((word) => `'${word}'`).join(' ')}`);

  const pwsh = findPowerShell();
  if (!pwsh) {
    assert.ok(!process.env.LLMS_REQUIRE_PINNED_TOOLS, 'PowerShell is missing; run `task deps:dev-tools`.');
    t.skip('PowerShell is not installed; run `task deps:dev-tools` to check this.');
    return;
  }
  const parsed = spawnSync(pwsh, ['-NoProfile', '-NonInteractive', '-EncodedCommand',
    Buffer.from(allStringWords, 'utf16le').toString('base64')], {
    env: { ...env, LLMS_TEST_SCRIPT: command }, encoding: 'utf8', timeout: 60000,
  });
  assert.equal(parsed.status, 0, parsed.stderr);
  assert.deepEqual(JSON.parse(parsed.stdout), [storageRoot, ...words]);
});
