# Git topology and subtrees

## Find the real coordination boundary

Run `git rev-parse --show-toplevel` from the target project. A Git subtree is an ordinary directory inside the parent worktree: it has no independent index. Use root-relative scope paths including its prefix, for example `vendor/engine/src/parser.py`. Agents in that subtree share the parent's board, lock, and Git owner.

A submodule or nested standalone repository has its own Git root and index. A linked worktree also has a separate index. Name each repository/worktree in cross-repository handoffs; do not apply the subtree rule to them.

The helper resolves the target from `--root`, not from the location of its own script. Invoking a helper vendored in a subtree still addresses the parent board. A board shipped inside a vendored copy is that package's historical log, not a second active board for the parent project.

## Coordinate a subtree operation

1. Record the parent worktree, exact prefix, remote/repository, ref, operation (`add`, `pull`, `split`, or `push`), and whether the project uses `--squash`. Use existing settings; do not assume all subtree imports use the same strategy.
2. The parent Git owner coordinates an edit pause for affected paths and confirms the index/worktree is ready for the operation. Check destination authorization for a push separately from ownership.
3. Inspect the incoming or outgoing diff, preserve unrelated work, and perform the requested operation. A subtree split changes path roots and synthesizes commit IDs; record the parent commit and split commit separately.
4. Validate the resulting tree and any integration checks, log the actual result or blocker, and explicitly release the pause. If Git conflicts remain, keep the operation blocked and coordinate resolution rather than reset or discard work.

For installing this skill as a subtree, the Git owner can use a destination such as `.agents/skills/message-board` and add a Claude discovery link to that same directory. Example, from a prepared consumer repository:

```sh
git subtree add --prefix=.agents/skills/message-board   https://github.com/tkarcheski/message-board.git main --squash
```

This is an example of an authorized Git-owner action, not an instruction to run it in every project. Update using the same prefix and agreed squash strategy. The consumer's active board remains at its own root.

## Logging across subtree exports

A parent-root `message-board.jsonl` is outside the subtree prefix and is not included in a subtree split. Never claim it was published to the subtree remote just because the parent was pushed.

If upstream requires a log, agree on a publishable package-local log/export under the subtree prefix. Keep it distinct from the live parent board and preserve source event IDs and prefix-to-root path mapping in the export description. Review destination-specific content, commit it under that prefix, then split and verify the resulting tree contains it. Do not duplicate the entire parent log or turn package-local exports into independent ownership authorities.

This skill repository's root JSONL log follows it when the whole repository is imported. That is package history. It does not transfer its recorded claims into the consuming project.

## Worktrees, clones, and the workstation

Use stable checkout locations under `~/Projects/`. Record the actual worktree/branch when handing work over. One Git owner controls each index. Worktree deletion and destructive cleanup require the user's authorization and preservation of useful work; never treat an idle session as abandoned data.

The helper's default lock is the current worktree's `git rev-parse --git-path message-board.lock`. It correctly handles `.git` files as well as directories. Different worktrees and clones do not share that lock or live log automatically. For shared runtime resources, designate one existing board as the authority, record its location in each project's instructions, and read/write it explicitly. Do not rely on eventual Git pushes or local locks to coordinate different machines. Distributed work needs a separately agreed transport/serialization mechanism.

When independent branches change a tracked JSONL log, resolve conflicts by preserving each unique event, preserving within-branch order and referenced dependencies, and documenting the reconciliation. Never use a union merge driver blindly or sort by wall-clock timestamp. Regenerate Markdown after the JSONL merge; don't merge two generated views by hand. New clones must re-establish active ownership rather than blindly inherit historical claims.

## Source

[Git's git-subtree documentation](https://github.com/git/git/blob/master/contrib/subtree/git-subtree.adoc) describes prefix selection, split history, and subtree operations. The ownership and logging rules above are this skill's coordination protocol.
