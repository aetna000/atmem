# `@atmem/client`

Typed Node 20+ client for AtMem's authenticated `/v1` API. The client preserves
structured authority, review, deletion, and error outcomes and applies an
overall abort timeout. It does not activate delivery or provider egress.

```ts
import {AtMemClient} from "@atmem/client";
const atmem = new AtMemClient({endpoint: "http://127.0.0.1:8765", token: process.env.ATMEM_TOKEN!});
await atmem.remember("Synthetic preference", "example-1");
console.log(await atmem.query("preference"));
```
