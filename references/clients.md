# Client setup

Use one maintained checkout at `~/Projects/message-board` on Omarchy/Linux. Symlink it into the skill locations needed by your clients. Do not replace an existing directory or link blindly; compare and deliberately retire stale copies. No Omarchy desktop or system configuration changes are required.

| Client | User skill location | Project skill location | Explicit use |
| --- | --- | --- | --- |
| Codex | `~/.agents/skills/message-board` | `.agents/skills/message-board` | `$message-board` |
| OpenCode | `~/.config/opencode/skills/message-board` | `.opencode/skills/message-board` | Ask to load `message-board` |
| Claude Code | `~/.claude/skills/message-board` | `.claude/skills/message-board` | `/message-board` |

Codex and OpenCode can share `~/.agents/skills/message-board`; OpenCode also discovers Claude-compatible directories. Avoid multiple discoverable copies with the same skill name. Some older Codex setups use `~/.codex/skills`; respect an existing working setup rather than installing a duplicate.

For Codex and OpenCode together, with Claude Code as a second reader:

```sh
mkdir -p ~/.agents/skills ~/.claude/skills
ln -s ~/Projects/message-board ~/.agents/skills/message-board
ln -s ~/Projects/message-board ~/.claude/skills/message-board
```

OpenCode can see both shared and Claude-compatible locations; check its discovered skill list and choose one configured source if your installed version reports duplicates. For an OpenCode-only installation, use its native directory instead:

```sh
mkdir -p ~/.config/opencode/skills
ln -s ~/Projects/message-board ~/.config/opencode/skills/message-board
```

The symlink commands intentionally fail if the target already exists. Review the client's skill list after installation and reload/restart the session as needed. Permissions and client configuration can disable skill discovery; do not silently broaden them.

## Project instructions

Add the same coordination policy to the project's existing agent instructions. Codex and OpenCode commonly use `AGENTS.md`; Claude Code uses `CLAUDE.md`. Preserve existing content and point both at the same policy, rather than maintaining competing protocols:

```text
Use the message-board skill before shared work. The canonical board is
message-board.jsonl at the Git worktree root; message-board.md is its readable
view. Use the common board lock and read current ownership before editing.
Claim exact paths, acknowledge handoffs, and use one Git owner per index.
Our board policy is versioned: commit and push reviewed JSONL and Markdown
checkpoints with the relevant work. Keep entries suitable for publication.
Keep durable artifacts under this project; do not create /tmp checkouts.
```

Change the publication sentence for projects whose owner has chosen private logging. The skill does not override an existing protocol. If a project consumes this repository as a subtree, see [Git topology](git-topology.md) before choosing the installation path.

## Client-neutral coordination

The `client` field describes the tool; `agent` identifies a specific session. A Claude session can ACK a Codex request, and OpenCode can act as Git owner. No client-specific messaging tool is required. All writers use the same JSONL schema and filesystem lock. Native messages are optional notifications, not the durable source of ownership.

## Sources

Discovery conventions checked against official documentation on 2026-10-02:

- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [OpenCode: Agent Skills](https://opencode.ai/docs/skills/)
- [Claude Code: Extend Claude with skills](https://code.claude.com/docs/en/skills)

This documents integration through skill files and a shared CLI. It does not claim automated end-to-end testing of all three client applications.
