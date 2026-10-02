# Coordination scenarios

These are fictional behavioral checks distilled from past coordination patterns. They can be used to review an agent's decisions without launching real concurrent agents.

| Situation | Expected action | Incorrect shortcut |
| --- | --- | --- |
| Coordinator assigns a file already claimed by another session | Request an explicit handoff; perform unrelated work meanwhile | Treat the assignment as ownership |
| A session stops replying while holding a claim | Record the blocker; seek release or explicit user reassignment | Take over after a timeout |
| Codex owns a file, Claude proposes a fix, OpenCode owns Git | Claude reviews read-only until handoff; OpenCode gets exact edit pauses before committing | Assume one client outranks another |
| Two writers read the same log head | One append succeeds; the other reads the new event and reassesses | Retry automatically with the new head |
| Worker passed tests but push failed | Record tests as passed and publication as blocked | Mark everything shipped |
| A new session resumes a summarized task | Read durable history, confirm owners and unacknowledged requests | Trust stale summary claims |
| Two worktrees want the same GPU | Use one explicit runtime owner and an acknowledged transfer | Assume separate indexes isolate hardware |
| An agent starts inside a subtree | Claim prefix-qualified paths on the parent board | Create a second parent-index Git owner |
| Parent log is outside a subtree being pushed | Verify export contents; publish an agreed scoped log if required | Say the parent log went upstream |
| JSONL append succeeds and Markdown refresh fails | Report the committed event ID, then regenerate the view | Append the same event again |
| Legacy board has a different schema | Continue its protocol; negotiate a migration checkpoint | Rewrite past records to fit the helper |
| Public logging is requested | Review and commit both JSONL and Markdown checkpoint | Ignore JSONL because boards were once private |

A coordinator should keep work useful, not merely keep agents busy. Assign only authorized, bounded outcomes with clear dependencies. A worker can report a genuine blocker and continue independent work; the board does not require waiting indefinitely on an unrelated task.
