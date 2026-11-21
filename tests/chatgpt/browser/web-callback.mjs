import assert from 'node:assert/strict';
import { createHash, randomBytes } from 'node:crypto';
import { once } from 'node:events';
import { createServer } from 'node:http';
import { chromium } from '@playwright/test';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const { base, email, password } = JSON.parse(input);
const client = 'atmem-test-client';
const callback = 'http://127.0.0.1:9901/callback';
const verifier = randomBytes(32).toString('base64url');
const state = randomBytes(24).toString('base64url');
const landing = createServer((req, res) => res.end('Returned to the app'));
let callbackQuery;
let callbackCount = 0;
const receiver = createServer((req, res) => {
  callbackCount += 1;
  callbackQuery = new URL(req.url, callback).searchParams;
  res.writeHead(303, { Location: 'http://127.0.0.1:' + landing.address().port + '/done' });
  res.end();
});

const browser = await chromium.launch();
try {
  landing.listen(0, '127.0.0.1');
  await once(landing, 'listening');
  receiver.listen(9901, '127.0.0.1');
  await once(receiver, 'listening');
  const page = await browser.newPage();
  let submissions = 0;
  let formActionBlocked = false;
  page.on('console', message => {
    if (message.text().includes('form-action')) formActionBlocked = true;
  });
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname.startsWith('/connect/')) {
      submissions += 1;
    }
  });
  const auth = new URL('/authorize', base);
  auth.search = new URLSearchParams({
    client_id: client, resource: base + '/mcp', redirect_uri: callback,
    response_type: 'code', scope: 'memory:read', state, code_challenge_method: 'S256',
    code_challenge: createHash('sha256').update(verifier).digest('base64url'),
  });
  await page.goto(auth.href);
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  const approve = page.getByRole('button', { name: 'Sign in and allow' });
  await approve.evaluate(button => {
    button.click();
    button.click();
  });
  try {
    await page.getByText('Returned to the app').waitFor({ timeout: 10000 });
  } catch {
    console.log(`OAuth browser handoff failed: form_action_blocked=${formActionBlocked} submissions=${submissions} callbacks=${callbackCount}`);
    throw new Error('Browser did not reach the callback landing page');
  }
  assert.equal(submissions, 1);
  assert.equal(callbackCount, 1);
  assert.ok(callbackQuery.get('state') === state && callbackQuery.has('code'));
  const token = await page.request.post(base + '/token', { form: {
    grant_type: 'authorization_code', client_id: client, resource: base + '/mcp',
    redirect_uri: callback, code: callbackQuery.get('code'), code_verifier: verifier,
  } });
  assert.equal(token.status(), 200);
} finally {
  await browser.close();
  receiver.close();
  landing.close();
}
