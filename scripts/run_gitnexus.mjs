import { pathToFileURL } from 'node:url';

const [node, , cli, ...args] = process.argv;
if (!cli) throw new Error('The pinned GitNexus CLI path is required.');
// GITNEXUS_STORAGE_PATH pins one index; inherited, it would point this run at
// another project's index.
delete process.env.GITNEXUS_STORAGE_PATH;
// analyze's estimated buffer pool (256 MiB floor) runs out on mid-size repos.
// Other commands, such as the long-lived MCP server, keep upstream's 2 GiB cap.
if (args[0] === 'analyze') process.env.GITNEXUS_LBUG_BUFFER_POOL_SIZE ??= String(4 * 1024 ** 3);
process.argv = [node, cli, ...args];
await import(pathToFileURL(cli).href);
