// Use the locked upstream parser; edit values without discarding comments.
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

try {
  const require = createRequire(pathToFileURL(process.argv[2]));
  const { parse, modify, applyEdits } = require('jsonc-parser');
  const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
  const errors = [];
  let text = payload.text;
  const data = parse(text, errors, { allowTrailingComma: true });
  if (errors.length || !data || Array.isArray(data) || typeof data !== 'object') {
    throw new Error('Invalid JSONC configuration.');
  }
  const object = value => value && typeof value === 'object' && !Array.isArray(value);
  const formattingOptions = { insertSpaces: true, tabSize: 2, eol: text.includes('\r\n') ? '\r\n' : '\n' };
  function update(before, after, prefix = []) {
    for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
      const path = [...prefix, key];
      if (object(before[key]) && object(after[key])) {
        update(before[key], after[key], path);
      } else if (JSON.stringify(before[key]) !== JSON.stringify(after[key])) {
        text = applyEdits(text, modify(text, path, after[key], { formattingOptions }));
      }
    }
  }
  if (payload.desired) update(data, payload.desired);
  console.log(JSON.stringify({ data, text }));
} catch {
  // Do not print configuration content or credentials on failure.
  console.error('JSONC parsing/editing failed; install the pinned tools and validate the configuration.');
  process.exitCode = 1;
}
