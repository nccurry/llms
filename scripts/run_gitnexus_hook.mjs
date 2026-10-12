// Keep upstream hook logic; select the local runtime and per-repository storage.
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [node, , storageRoot, hook, ...args] = process.argv;
if (!storageRoot || !hook) throw new Error('The storage root and upstream hook path are required.');
delete process.env.GITNEXUS_STORAGE_PATH;
process.env.GITNEXUS_STORAGE_ROOT = storageRoot;
process.env.PATH = [path.dirname(node), process.env.PATH ?? ''].join(path.delimiter);
process.argv = [node, hook, ...args];
await import(pathToFileURL(hook).href);
