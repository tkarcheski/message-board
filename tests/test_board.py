"""Behavioral tests with isolated fixtures inside the maintained checkout."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / 'scripts' / 'board.py'
SPEC = importlib.util.spec_from_file_location('board', SCRIPT)
board = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(board)


def entry(identifier='first', client='codex', **changes):
    result = {'id': identifier, 'agent': f'{client}-worker-1', 'client': client,
              'type': 'CLAIM', 'to': ['all'], 'scope': ['src/parser.py'],
              'message': 'Claim a bounded parser fix.', 'verification': 'not run',
              'next': 'Implement then verify.'}
    result.update(changes)
    return result


class BoardTests(unittest.TestCase):
    def setUp(self):
        fixtures = PROJECT / '.test-work'
        fixtures.mkdir(exist_ok=True)
        self.fixture = tempfile.TemporaryDirectory(prefix='board-', dir=fixtures)
        self.addCleanup(self.fixture.cleanup)
        self.base = Path(self.fixture.name)
        self.root = self.base / 'parent'
        self.root.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1', GIT_CEILING_DIRECTORIES=str(PROJECT),
                        GIT_AUTHOR_NAME='Board Test', GIT_AUTHOR_EMAIL='test@example.invalid',
                        GIT_COMMITTER_NAME='Board Test', GIT_COMMITTER_EMAIL='test@example.invalid',
                        TMPDIR=str(self.base), TMP=str(self.base), TEMP=str(self.base),
                        PYTHONDONTWRITEBYTECODE='1')
        self.git('init', '-b', 'main')

    def git(self, *args, root=None):
        result = subprocess.run(['git', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null',
                                 '-C', str(root or self.root), *args],
                                capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def cli(self, *args, data=None, root=None):
        return subprocess.run([sys.executable, str(SCRIPT), '--root', str(root or self.root), *args],
                              input=json.dumps(data) if data is not None else None,
                              capture_output=True, text=True, env=self.env)

    def post(self, data=None, expected='EMPTY', root=None):
        result = self.cli('append', '--expect', expected, data=data or entry(), root=root)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def log(self):
        return [json.loads(line) for line in (self.root / 'message-board.jsonl').read_text().splitlines()]

    def test_empty_status_and_no_accidental_initialization(self):
        result = self.cli('status')
        self.assertEqual(json.loads(result.stdout), {'head': 'EMPTY', 'count': 0, 'events': []})
        self.assertFalse((self.root / 'message-board.jsonl').exists())

    def test_three_clients_handoff_and_unicode_round_trip(self):
        first = self.post(entry(message='Claim café parser: $HOME and `literal` stay data.'))
        self.post(entry('second', 'claude', type='REQUEST', refs=['first']), 'first')
        self.post(entry('third', 'opencode', type='ACK', refs=['second']), 'second')
        self.assertEqual([e['client'] for e in self.log()], ['codex', 'claude', 'opencode'])
        self.assertIn('café', first['message'])
        self.assertTrue(first['ts'].endswith('+00:00'))
        self.assertEqual(self.cli('check').returncode, 0)

    def test_concurrent_stale_writers_have_one_winner(self):
        def send(number):
            return self.cli('append', '--expect', 'EMPTY', data=entry(f'writer-{number}'))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(send, range(8)))
        self.assertEqual(sum(r.returncode == 0 for r in results), 1)
        self.assertTrue(all('stale head' in r.stderr for r in results if r.returncode))
        self.assertEqual(len(self.log()), 1)
        self.assertEqual(self.cli('check').returncode, 0)

    def test_duplicate_id_and_unknown_reference_do_not_modify_log(self):
        self.post()
        before = (self.root / 'message-board.jsonl').read_bytes()
        for candidate in [entry(), entry('second', refs=['missing'])]:
            result = self.cli('append', '--expect', 'first', data=candidate)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((self.root / 'message-board.jsonl').read_bytes(), before)

    def test_invalid_records_are_rejected_before_writing(self):
        bad = [entry(schema=True), entry(ts='2026-10-02T12:00:00'),
               entry(scope=['../outside']), entry(scope=['/absolute']), entry(to=[]),
               entry(type='MAGIC'), entry(id='EMPTY'), entry(client='bad\nclient'),
               entry(unknown='typo'), entry(refs='first'), entry(scope=['src/a', 'src/a'])]
        for candidate in bad:
            with self.subTest(candidate=candidate):
                result = self.cli('append', '--expect', 'EMPTY', data=candidate)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / 'message-board.jsonl').exists())

    def test_dot_scope_and_runtime_scope_are_valid(self):
        self.post(entry(scope=['.', 'resource:gpu:0', 'git:index']))
        self.assertEqual(self.cli('check').returncode, 0)

    def test_repeated_json_key_is_rejected(self):
        with self.assertRaisesRegex(board.BoardError, 'duplicate JSON key'):
            board.decode('{"id":"one","id":"two"}')

    def test_legacy_markdown_and_legacy_jsonl_are_preserved(self):
        path = self.root / 'message-board.md'
        path.write_text('# Existing private history\n')
        result = self.cli('append', '--expect', 'EMPTY', data=entry())
        self.assertIn('legacy Markdown', result.stderr)
        self.assertEqual(path.read_text(), '# Existing private history\n')
        legacy = '{"from":"worker","body":"old history"}\n'
        (self.root / 'message-board.jsonl').write_text(legacy)
        result = self.cli('render')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_text(), '# Existing private history\n')
        self.assertEqual((self.root / 'message-board.jsonl').read_text(), legacy)

    def test_corrupt_tail_is_preserved(self):
        self.post()
        path = self.root / 'message-board.jsonl'
        with path.open('ab') as handle:
            handle.write(b'{"id":"torn')
        before = path.read_bytes()
        result = self.cli('append', '--expect', 'first', data=entry('second'))
        self.assertIn('incomplete final line', result.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_missing_view_can_be_recovered_without_changing_log(self):
        self.post()
        before = (self.root / 'message-board.jsonl').read_bytes()
        (self.root / 'message-board.md').unlink()
        self.assertNotEqual(self.cli('check').returncode, 0)
        self.assertEqual(self.cli('render').returncode, 0)
        self.assertEqual(self.cli('check').returncode, 0)
        self.assertEqual((self.root / 'message-board.jsonl').read_bytes(), before)

    def test_failed_render_retains_committed_event(self):
        root, lock = board.location(self.root)
        with board.locked(lock), patch.object(board, 'render', side_effect=OSError('disk unavailable')):
            with self.assertRaisesRegex(board.BoardError, 'first IS in JSONL'):
                board.append(root, [], entry(), 'EMPTY')
        self.assertEqual(len(self.log()), 1)
        self.assertEqual(self.cli('render').returncode, 0)
        self.assertEqual(self.cli('check').returncode, 0)

    def test_markdown_escapes_untrusted_markup_and_detects_drift(self):
        self.post(entry(message='<script>alert(1)</script>\n## fake event'))
        path = self.root / 'message-board.md'
        view = path.read_text()
        self.assertNotIn('<script>', view)
        self.assertIn('&lt;script&gt;', view)
        path.write_text(view + '\nmanual edit\n')
        result = self.cli('append', '--expect', 'first', data=entry('second'))
        self.assertIn('differs from JSONL', result.stderr)
        self.assertEqual(len(self.log()), 1)
        self.assertEqual(self.cli('render').returncode, 0)
        self.assertEqual(path.read_text(), view)

    def test_symlink_log_cannot_redirect_writes(self):
        outside = self.base / 'outside.jsonl'
        outside.write_text('private data\n')
        (self.root / 'message-board.jsonl').symlink_to(outside)
        result = self.cli('append', '--expect', 'EMPTY', data=entry())
        self.assertIn('refusing symlink', result.stderr)
        self.assertEqual(outside.read_text(), 'private data\n')

    def test_actual_subtree_uses_parent_board_and_split_excludes_parent_log(self):
        upstream = self.base / 'upstream'
        upstream.mkdir()
        self.git('init', '-b', 'main', root=upstream)
        (upstream / 'engine.txt').write_text('engine\n')
        self.post(entry('package-history', scope=['engine.txt']), root=upstream)
        package_log = (upstream / 'message-board.jsonl').read_bytes()
        self.git('add', 'engine.txt', 'message-board.jsonl', 'message-board.md', root=upstream)
        self.git('commit', '-m', 'Seed package', root=upstream)
        (self.root / 'README.md').write_text('parent\n')
        self.git('add', 'README.md')
        self.git('commit', '-m', 'Seed parent')
        self.git('subtree', 'add', '--prefix=vendor/engine', str(upstream), 'main', '--squash')
        nested = self.root / 'vendor/engine'
        self.post(entry(scope=['vendor/engine/engine.txt']), root=nested)
        self.assertTrue((self.root / 'message-board.jsonl').exists())
        self.assertEqual((nested / 'message-board.jsonl').read_bytes(), package_log)
        self.assertEqual(board.location(nested), board.location(self.root))
        self.git('add', 'message-board.jsonl', 'message-board.md')
        self.git('commit', '-m', 'Record parent coordination')
        split = self.git('subtree', 'split', '--prefix=vendor/engine')
        names = self.git('ls-tree', '-r', '--name-only', split).splitlines()
        self.assertEqual(names, ['engine.txt', 'message-board.jsonl', 'message-board.md'])
        exported = json.loads(self.git('show', f'{split}:message-board.jsonl'))
        self.assertEqual(exported['id'], 'package-history')
        self.assertEqual(self.log()[0]['id'], 'first')

    def test_linked_worktree_has_its_own_board_and_lock(self):
        (self.root / 'README.md').write_text('parent\n')
        self.git('add', 'README.md')
        self.git('commit', '-m', 'Seed parent')
        linked = self.base / 'linked'
        self.git('worktree', 'add', '-b', 'worker', str(linked))
        self.post(root=linked)
        self.assertTrue((linked / '.git').is_file())
        self.assertFalse((self.root / 'message-board.jsonl').exists())
        self.assertNotEqual(board.location(linked)[1], board.location(self.root)[1])
        self.assertEqual(self.cli('check', root=linked).returncode, 0)

    def test_cli_requires_a_git_worktree(self):
        result = self.cli('status', root=self.base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not a git repository', result.stderr)


if __name__ == '__main__':
    unittest.main()
