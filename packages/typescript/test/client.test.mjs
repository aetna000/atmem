import assert from "node:assert/strict";
import test from "node:test";
import {AtMemClient, AtMemAPIError} from "../dist/index.js";

test("preserves typed authority outcomes", async () => {
  const calls = [];
  const client = new AtMemClient({endpoint: "http://127.0.0.1:1", token: "secret", fetch: async (url, init) => {
    calls.push({url, init});
    return new Response(JSON.stringify({format: "atmem-api-mutation-result-v1", result: {accepted: true}, request_id: "req_1", idempotent_replay: false}), {status: 200, headers: {"Content-Type": "application/json"}});
  }});
  const value = await client.remember("synthetic", "key-1");
  assert.equal(value.result.accepted, true);
  assert.equal(calls[0].init.headers.Authorization, "Bearer secret");
});

test("does not hide structured errors", async () => {
  const client = new AtMemClient({endpoint: "http://127.0.0.1:1", token: "bad", fetch: async () => new Response(JSON.stringify({format: "atmem-api-error-v1", error: {code: "forbidden", message: "denied"}, request_id: "req_2"}), {status: 403, headers: {"Content-Type": "application/json"}})});
  await assert.rejects(client.health(), error => error instanceof AtMemAPIError && error.body.error.code === "forbidden");
});
