import assert from 'node:assert/strict';
import { extractHookContexts, extractTypeFields } from './lib/hook-context-shape.mjs';
const source = `type OpenClawPluginToolContextBase = {
  senderIsOwner?: boolean;
  sessionId?: string;
};
type OpenClawPluginToolContext<Version extends 1 | 2 = 1> = Version extends 2 ? OpenClawPluginToolContextBase & {
  assertInvocationCurrent: () => void;
} : OpenClawPluginToolContextBase;`;
assert.deepEqual(extractTypeFields(source, 'OpenClawPluginToolContext'), [
  {name: 'senderIsOwner', optional: true}, {name: 'sessionId', optional: true},
]);
assert.equal(extractTypeFields(source.replace('= 1>', '= 2>'), 'OpenClawPluginToolContext'), null);
assert.equal(extractTypeFields(source.replace('} : OpenClawPluginToolContextBase;', '} : UnknownContext;'), 'OpenClawPluginToolContext'), null);
assert.deepEqual(extractTypeFields(source.replace('  senderIsOwner?: boolean;\n', ''), 'OpenClawPluginToolContext'), [{name: 'sessionId', optional: true}]);

const inheritedSource = `
type PluginHookContextWindow = {
  sessionId?: string;
  sessionKey?: string;
};
type PluginHookAgentContext = PluginHookContextWindow & {
  agentId?: string;
};
type PluginHookHandlerMap = {
  before_prompt_build: AsyncPluginHook<PromptEvent, PluginHookAgentContext, PromptResult>;
};`;
assert.deepEqual(extractTypeFields(inheritedSource, 'PluginHookAgentContext'), [
  {name: 'sessionId', optional: true},
  {name: 'sessionKey', optional: true},
  {name: 'agentId', optional: true},
]);
assert.deepEqual(extractHookContexts([inheritedSource]), {
  before_prompt_build: 'PluginHookAgentContext',
});
console.log('hook-context parser: default-v1 alias and fail-closed changes verified');
