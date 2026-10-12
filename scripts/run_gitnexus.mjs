// An inherited single-index override must not redirect another project/worktree.
import { pathToFileURL } from 'node:url';

const [node, , cli, ...args] = process.argv;
if (!cli) throw new Error('The pinned GitNexus CLI path is required.');
delete process.env.GITNEXUS_STORAGE_PATH;
process.argv = [node, cli, ...args];
await import(pathToFileURL(cli).href);
