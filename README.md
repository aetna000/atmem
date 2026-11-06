# AtMem for Codex

AtMem is a public pilot for saving and recalling personal or project memories across chats. Memory lives in your signed-in AtMem cloud account. You choose what to save and review each change before it is committed.

## Install

Use a Codex CLI that supports plugin marketplaces and MCP OAuth sign-in.

```sh
codex plugin marketplace add aetna000/atmem --ref codex-marketplace
codex plugin add atmem-chatgpt@atmem
codex mcp login atmem --scopes memory:read,memory:write,memory:delete
```

Open the sign-in page on the computer running Codex. Register or sign in with AtMem and verify your email if prompted. For read-only access, request just `memory:read`. Start a new Codex chat after connecting.

## Try it

Ask Codex to use AtMem to remember “My sample project codename is Copper Heron.” Open the approval link, check the text and scope, and approve. Ask Codex to finish the save and show the receipt. In a new chat, ask AtMem for the sample project codename. You can ask to forget the sample using the same review and approval flow.

## Disconnect and remove

```sh
codex mcp logout atmem
codex plugin remove atmem-chatgpt@atmem
```

Removing the plugin leaves your cloud memories in your account. To delete the account, use the [AtMem account deletion page](https://atmem-chatgpt-nvwvv4d7sa-uc.a.run.app/account/delete).

Report problems in the [AtMem issue tracker](https://github.com/aetna000/atmem/issues). Keep memory contents and sign-in details private.
