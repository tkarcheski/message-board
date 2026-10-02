# Message Board

A small agent skill for coordinating multiple agents in one shared repository.

Agents use a local, append-only `message-board.md` to claim files, acknowledge handoffs, report evidence, and agree on one Git owner. An exclusive `flock` serializes board updates. Ownership stays explicit: an assignment, timeout, or silent agent does not transfer a claim.

The full protocol lives in [SKILL.md](SKILL.md).

## Install

Clone this repository into your agent’s skill directory. For a Codex installation using `~/.codex/skills`:

```sh
git clone https://github.com/tkarcheski/message-board.git ~/.codex/skills/message-board
```

If that directory already exists, compare it with this repository before replacing your local skill.

## Use

Ask your agent:

```text
Use $message-board to coordinate with the other agents working in this repository.
Read the existing board before editing, claim exact files, and keep Git ownership explicit.
```

To make the convention part of a project, add guidance to its `AGENTS.md` asking agents to read and follow the existing board before work. Keep `message-board.md` and `tmp/message-board.lock` out of published commits, using local Git excludes when appropriate.

## Example

This fictional exchange illustrates the workflow; it is not a transcript from a real project:

1. Agent A claims `src/parser.py` for a parser fix.
2. Agent B claims `docs/parser.md` for the matching documentation update.
3. Agent C requests Git ownership. The participating agents acknowledge it explicitly.
4. A and B report the exact files changed and their verification, then acknowledge an edit pause for the commit candidate.
5. C inspects the staged diff, verifies the candidate, commits, and posts the SHA and release of the pause.

Actual entries include a timestamp, session, type, unique ID, recipient, scope, message, verification, and next action. See the template in [SKILL.md](SKILL.md).

## Boundaries

This is a cooperative protocol, not a scheduler or access-control system. Every writer must use the same lock for serialized posting. The lock protects board appends; it does not enforce file claims or Git ownership. Board entries do not authorize runtime changes, external messages, or destructive actions. Keep secrets and private logs off the board, and never publish a live board as an example.

## Validation

The skill is a single Markdown file with YAML frontmatter and has no runtime dependencies. Its locked-append protocol assumes an environment providing `flock`.
