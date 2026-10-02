# Durable logging

## Files and locks

For new boards, `message-board.jsonl` is canonical; `message-board.md` is a deterministic readable view. Events are logically append-only in both. The helper atomically replaces the generated Markdown file after appending JSONL, so agents must not independently edit that view. A pair of filesystem files cannot be updated as one atomic transaction: if rendering fails, the JSONL event remains committed and the view is recoverable.

The default lock is resolved by `git rev-parse --git-path message-board.lock`. On Omarchy/Linux, Python's `fcntl.flock` serializes cooperating local writers. All reads/checks/appends made by the helper use this same exclusive lock. Never delete or replace a live lock inode. Hold it only for board operations, not tests, commits, model inference, or waiting on another agent. Existing boards with a different agreed lock must keep that lock until all writers coordinate a migration; do not mix the helper with their old writer.

The helper requires Python 3.10+, Git, and POSIX locking. It uses no third-party dependencies or `/tmp` files. It does not enforce claims, infer consent, send messages, call model APIs, stage files, or push Git.

## Event schema

One UTF-8 JSON object per newline-terminated line. The helper uses this schema for new boards; other historical schemas require migration rather than silent coercion.

| Field | Meaning |
| --- | --- |
| `schema` | Integer `1` |
| `id` | Globally unique stable ID; generated UUID by default |
| `ts` | Actual ISO timestamp with timezone; generated UTC timestamp by default |
| `agent` | Unique stable session identifier |
| `client` | `codex`, `opencode`, `claude`, `human`, or another tool identifier |
| `type` | `CLAIM`, `REQUEST`, `ASSIGN`, `ACK`, `UPDATE`, `BLOCKED`, `HANDOFF`, `RELEASE`, `DECISION`, `CORRECTION` |
| `to` | Nonempty array of session identifiers, or `["all"]` |
| `scope` | Nonempty array of exact root-relative paths, directory scopes ending in `/`, `git:<role/scope>`, or `resource:<resource-id>` |
| `message` | Concise decision or status; for claims, include the bounded outcome |
| `verification` | Actual evidence, limitations, or `not run` |
| `next` | Specific next action, needed ACK, or release |
| `refs` | Optional array of earlier event IDs in the same log |

All fields except `refs` are required in stored records. `append` fills omitted `schema`, `id`, `ts`, and `refs`. Custom clients are allowed. There is no required sequence counter: append order defines local order and event IDs survive export/merge. Timestamps record observation time, not distributed consensus. Unknown fields, repeated keys/IDs, malformed lines, missing reference targets, and unterminated final lines are rejected.

Use `scope` for files or named resources, not paragraphs. Claims on a directory include its descendants; the helper validates syntax but does not compute overlapping ownership. Put repository/worktree identity in cross-board handoff messages, and use the appropriate board for each index. Do not include private absolute machine paths in publishable logs.

## Commands

From a target repository, with the skill checkout at `~/Projects/message-board`:

```sh
python3 ~/Projects/message-board/scripts/board.py --root . status
python3 ~/Projects/message-board/scripts/board.py --root . status --tail 10
python3 ~/Projects/message-board/scripts/board.py --root . check
```

`status` reports `head`, `count`, and events. By default it includes the full history. A tail is not an active-claim summary: read earlier entries when unresolved ownership depends on them.

Use the [README example](../README.md#start-a-new-project-board) to append a JSON object through a quoted heredoc. For an existing log, `--expect` must match the final event you read. Another writer can post between your review and append: the helper checks under the lock and rejects the stale head. Read those new events and reassess your claim or request before submitting again. Never add an automatic retry loop that bypasses this review.

The input is data, never shell interpolation. `--entry path/to/event.json` also accepts a prepared object; keep useful artifacts in the project rather than `/tmp`. `--root` resolves the target Git root, so running from inside a subtree reaches the same parent board. Script location does not select a board.

## Recovery

- **Missing or stale generated Markdown:** inspect JSONL and any changed view. `python3 ~/Projects/message-board/scripts/board.py --root . render` recreates the view from valid records. A non-generated legacy Markdown file is never overwritten automatically.
- **Failure after JSONL append:** the error names the committed event ID. Check the log, then repair the view. Do not post a duplicate event. If a process was killed before reporting an ID, inspect the log before retrying.
- **Truncated or malformed JSONL:** stop writers, preserve the damaged bytes in a project-local recovery artifact, and agree on a repair with the owner. The helper will not guess or silently delete history. Restore a verified checkpoint and reconcile preserved later events with a documented recovery record when appropriate.
- **Semantic error:** append `CORRECTION` referring to the original ID; do not alter old events.
- **Sensitive data accidentally logged:** stop publication and follow the owner's redaction/credential-response process. Append-only coordination is not a reason to publish a secret. Do not place secret material in a correction either.

## Legacy migration

Existing projects may have Markdown only, a `from/body/created_at` JSONL format, optional sequence counters, or other conventions. Continue reading their actual schema and using their lock while planning migration. Do not run this helper against them as though they were empty.

The coordinator obtains an explicit writer pause and records a cutover plan: old format and last event, new schema/paths/lock, publication policy, active claims, and next owner. Preserve the original history in a clearly named project-local legacy file; don't stage a private archive just because the new board is public. Summarize only the necessary active state into a new `DECISION` event with provenance to the legacy checkpoint. All writers acknowledge the switch before resuming. Keep the legacy record readable until its unresolved handoffs are closed. Historical timestamps and claims must not be invented or silently rewritten.

## Committing a checkpoint

This repository has explicit authorization to publish its JSONL and Markdown. Consumer repositories must follow their own owner's publication policy. Public summaries should name task outcomes, relative paths, checks, and next actions without copying transcripts or private operational details.

1. The Git owner obtains edit pauses for the candidate and briefly coordinates a board-writing pause to select a checkpoint ID. Do not hold the filesystem lock across Git operations.
2. Run `check`; review the full diff for both files and the selected source paths. Stage exact paths, including **both** `message-board.jsonl` and `message-board.md`. Inspect the staged pair to confirm it represents the same checkpoint. Preserve unrelated staged content.
3. Release the board-writing pause once the staged snapshot is verified; later appends can remain unstaged for the next commit. Commit the verified snapshot and push the authorized branch. Verify the remote commit and presence of its JSONL blob, not just local success.
4. Append a later event reporting the SHA and actual push evidence. That event belongs to a subsequent checkpoint. A commit cannot include its own SHA; do not amend in a loop trying to achieve that.

The pair is a historical checkpoint, not a real-time distributed coordination service. Keep lock files, fixtures, and private recovery material out of commits. For subtree exports, follow [the export boundary rules](git-topology.md#logging-across-subtree-exports).
