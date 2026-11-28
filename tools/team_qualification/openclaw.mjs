// Exercise the installed host's MCP catalog, materialized tool and agent result.
import {readFile, readdir} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
const spec = JSON.parse(await readFile(process.argv[2], 'utf8'));
const dist = spec.openclawDist;
const entries = (await readdir(dist)).filter(name => /^agent-bundle-mcp-tools-.*\.js$/.test(name));
let createRuntime;
for (const file of entries) {
  const exports = await import(pathToFileURL(path.join(dist,file)));
  if (exports.createBundleMcpToolRuntime) createRuntime = exports.createBundleMcpToolRuntime;
}
if (!createRuntime) throw Error('Installed OpenClaw MCP runtime export unavailable');
const runtime = await createRuntime({workspaceDir:spec.workspace, cfg:{plugins:{enabled:false},
  mcp:{servers:{atmem_team:spec.server}}}, reservedToolNames:new Set()});
try {
  const tool = runtime.tools.find(tool => tool.name.endsWith(spec.tool));
  if (!tool) throw Error('Host tools: ' + runtime.tools.map(t=>t.name).join(','));
  const reply = await tool.execute('team-qualification',spec.args);
  if (reply.details?.isError) throw Error('OpenClaw tool returned an error');
  process.stdout.write(JSON.stringify({tool:tool.name,reply})+'\n');
} finally {await runtime.dispose();}
