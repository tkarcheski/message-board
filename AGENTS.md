# Repository work

Read SKILL.md and the current message-board.jsonl before edits. Follow the shared protocol. This repository versions and publishes both message-board.jsonl and its generated message-board.md; entries must be suitable for public GitHub. Use scripts/board.py for new events and do not hand-edit the generated view.

Use a stable session, exact file claims, and one acknowledged Git owner per index. Initial publisher skill-publisher bootstrapped ownership; consult later events for its release or transfer. Preserve unrelated work.

Keep the checkout under ~/Projects/message-board. Tests use .test-work/ inside this repository, never /tmp. Validate with python3 -m unittest discover -s tests -v, python3 scripts/board.py --root . check, and git diff --check. Do not claim three-client end-to-end testing unless it was actually performed.
