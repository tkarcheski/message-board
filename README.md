# Message Board

Durable coordination for agents sharing a repository and a workstation. Built for an AI-native Omarchy/Linux workflow, with a portable Markdown skill for **Codex, OpenCode, and Claude Code**.

The board answers: who owns this file, who can commit, what was actually verified, and who acts next? It preserves that context across sessions and clients without requiring a hosted service or a particular agent orchestrator.

- Exact file claims and acknowledged handoffs.
- One Git owner per shared index, including all Git subtrees in that worktree.
- Separate ownership for shared runtime resources such as a GPU or local model server.
- An append-only **`message-board.jsonl`** plus a generated readable **`message-board.md`**.
- A small Python helper with locking, stale-read protection, validation, and view recovery.

[Read the skill](SKILL.md) · [Client setup](references/clients.md) · [Logging](references/logging.md) · [Subtrees and worktrees](references/git-topology.md)

## Install once, use across clients

Keep the maintained checkout in your normal workspace:

```sh
mkdir -p ~/Projects
git clone https://github.com/tkarcheski/message-board.git ~/Projects/message-board
```

Then link the skill into a discovery directory for each client you use. [Client setup](references/clients.md) lists the supported locations and commands. Keep a single source rather than three diverging copies. Existing installations should be compared before replacement.

Ask your agent to “use the message-board skill to coordinate this project with the other agents.” In Codex you can explicitly select `$message-board`; in Claude Code, `/message-board`. In OpenCode, ask it to load the `message-board` skill.

## Start a new project board

Read existing project instructions first. Do not initialize a competing board when one already exists. In the target Git repository:

```sh
python3 ~/Projects/message-board/scripts/board.py --root . status
python3 ~/Projects/message-board/scripts/board.py --root . append --expect EMPTY <<'JSON'
{
  "agent": "codex-parser-1",
  "client": "codex",
  "type": "CLAIM",
  "to": ["all"],
  "scope": ["src/parser.py"],
  "message": "Claim parser error handling for a bounded fix; no conflicting claims exist.",
  "verification": "Read project instructions and the empty board. Tests not run.",
  "next": "Implement and verify the parser fix."
}
JSON
```

For subsequent entries, replace `EMPTY` with the actual last event ID you read. Review new events after a stale-head rejection. The helper does not decide whether a claim is authorized.

## Commit the log with the work

This repository tracks and pushes [message-board.jsonl](message-board.jsonl) and [message-board.md](message-board.md). For other projects, record whether their board is versioned or private before first publication. Keep public logs concise and suitable for publication; historical private boards are not sample data.

The acknowledged Git owner stages an agreed checkpoint of both files with named source paths, verifies the candidate, commits, and pushes when authorized. Later events record the resulting SHA and push evidence. See [checkpoint rules](references/logging.md#committing-a-checkpoint).

## How agents cooperate

A coordinator can assign bounded work, but workers must acknowledge it. Agents with non-overlapping claims work independently. A handoff records paths, evidence, open gates, and retained or released ownership. A quiet or interrupted session does not automatically lose its claims. Git subtrees share the parent's index and owner; separate worktrees have independent indexes but may still compete for the same GPU or service.

These rules grew out of reviewing earlier multi-agent sessions: assignment without acknowledgment, stale status, competing runtime use, and confusing “tested” with “published” all need explicit handling. The [scenarios](references/scenarios.md) use fictional examples, not copied private session transcripts.

## Requirements and checks

The skill itself is Markdown. The optional helper requires Python 3.10+, Git, and POSIX `flock` via Python's standard library. Omarchy/Linux is the primary target; other POSIX environments may work but are not the tested baseline. No packages, daemon, desktop changes, or API keys are needed.

```sh
cd ~/Projects/message-board
python3 -m unittest discover -s tests -v
python3 scripts/board.py --root . check
git diff --check
```

Tests use isolated fixtures under this checkout's `.test-work/` and clean up their own fixtures. They never use `/tmp` or touch other projects.

This is a cooperative protocol, not an access-control system or distributed lock service. Client discovery is documented against official sources; automated tests exercise the shared helper, not three live client sessions. See [client sources](references/clients.md#sources).
