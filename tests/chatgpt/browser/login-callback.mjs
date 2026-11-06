import { chromium } from '@playwright/test';
import { createServer } from 'node:http';
import { randomBytes, createHash } from 'node:crypto';
import { once } from 'node:events';
import assert from 'node:assert/strict';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const { base, email, password } = JSON.parse(input);
const state = randomBytes(24).toString('base64url');
const verifier = randomBytes(32).toString('base64url');
const client = 'https://chatgpt.com/oauth/codex/client.json';
const listener = createServer((req, res) => {
  res.end('Account connected');
});
listener.listen(0, '127.0.0.1');
await once(listener, 'listening');
const callback = 'http://127.0.0.1:' + listener.address().port + '/callback';
const browser = await chromium.launch();
try {
  const auth = new URL('/authorize', base);
  auth.search = new URLSearchParams({client_id:client, resource:base+'/mcp', redirect_uri:callback,
    response_type:'code', scope:'memory:read', state, code_challenge_method:'S256',
    code_challenge:createHash('sha256').update(verifier).digest('base64url')});
  const page = await browser.newPage();
  await page.goto(auth.href);
  await page.getByLabel('Email', {exact:true}).fill(email);
  await page.getByLabel('Password', {exact:true}).fill(password);
  await page.getByRole('button', {name:'Sign in and allow'}).click();
  await page.waitForURL(url => url.origin + url.pathname === callback, {timeout:12000});
  const params = new URL(page.url()).searchParams;
  assert.equal(params.get('state'), state);
  const token = await page.request.post(base+'/token', {form:{grant_type:'authorization_code',
    client_id:client, resource:base+'/mcp', redirect_uri:callback, code:params.get('code'), code_verifier:verifier}});
  assert.equal(token.status(), 200);
} finally {
  await browser.close();
  listener.close();
}
