#!/usr/bin/env python3
"""Local JSONL coordination log; Python standard library, Git, POSIX only."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import uuid

HEADER = '# Message board\n\nGenerated from `message-board.jsonl`; do not edit this view.\n'
TYPES = {'CLAIM', 'REQUEST', 'ASSIGN', 'ACK', 'UPDATE', 'BLOCKED', 'HANDOFF',
         'RELEASE', 'DECISION', 'CORRECTION'}
FIELDS = {'schema', 'id', 'ts', 'agent', 'client', 'type', 'to', 'scope',
          'message', 'verification', 'next', 'refs'}


class BoardError(Exception):
    pass


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BoardError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def decode(text):
    try:
        return json.loads(text, object_pairs_hook=unique_keys)
    except json.JSONDecodeError as exc:
        raise BoardError(f'invalid JSON: {exc}') from exc


def validate(event):
    if not isinstance(event, dict):
        raise BoardError('event must be a JSON object')
    missing = FIELDS - {'refs'} - event.keys()
    extra = event.keys() - FIELDS
    if missing or extra:
        raise BoardError(f'fields missing={sorted(missing)}, unknown={sorted(extra)}')
    if type(event['schema']) is not int or event['schema'] != 1:
        raise BoardError('schema must be integer 1')
    for key in ('id', 'ts', 'agent', 'client', 'type', 'message', 'verification', 'next'):
        if not isinstance(event[key], str) or not event[key].strip():
            raise BoardError(f'{key} must be a nonempty string')
        if any(ord(c) < 32 and c not in '\n\t' for c in event[key]):
            raise BoardError(f'{key} contains a control character')
    for key in ('id', 'agent', 'client'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', event[key]):
            raise BoardError(f'{key} must be a short stable identifier')
    if event['id'] == 'EMPTY':
        raise BoardError('EMPTY is reserved for an empty log')
    if event['type'] not in TYPES:
        raise BoardError(f'unsupported event type: {event["type"]}')
    try:
        timestamp = datetime.fromisoformat(event['ts'].replace('Z', '+00:00'))
        if timestamp.utcoffset() is None:
            raise ValueError('timezone missing')
    except ValueError as exc:
        raise BoardError('ts must be an ISO timestamp with a timezone') from exc
    for key in ('to', 'scope', 'refs'):
        values = event.get(key, [])
        if not isinstance(values, list) or any(
            not isinstance(v, str) or not v.strip() or '\n' in v or '\r' in v
            for v in values
        ):
            raise BoardError(f'{key} must be an array of nonempty single-line strings')
        if key != 'refs' and not values:
            raise BoardError(f'{key} must not be empty')
        if len(set(values)) != len(values):
            raise BoardError(f'{key} contains duplicates')
    for scope in event['scope']:
        if scope.startswith(('resource:', 'git:')):
            continue
        path = PurePosixPath(scope)
        if path.is_absolute() or '..' in path.parts or '\\' in scope or '~' == path.parts[0]:
            raise BoardError('file scopes must be root-relative POSIX paths without ..')
    return event


def git(directory, *args):
    result = subprocess.run(['git', '-C', str(directory), 'rev-parse', *args],
                            text=True, capture_output=True)
    if result.returncode:
        raise BoardError(result.stderr.strip() or 'cannot resolve Git worktree')
    return result.stdout.strip()


def location(directory):
    root = Path(git(directory, '--show-toplevel')).resolve()
    lock = Path(git(root, '--git-path', 'message-board.lock'))
    if not lock.is_absolute():
        lock = root / lock
    for path in (root / 'message-board.jsonl', root / 'message-board.md', lock):
        if path.is_symlink():
            raise BoardError(f'refusing symlink board or lock: {path.name}')
    return root, lock


@contextmanager
def locked(lock):
    # A stable lock inode is kept in Git metadata, never in /tmp or in commits.
    with lock.open('a', encoding='utf-8') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def read_events(root):
    path = root / 'message-board.jsonl'
    if not path.exists():
        if (root / 'message-board.md').exists():
            raise BoardError('legacy Markdown board exists; agree on migration first')
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise BoardError('log has an incomplete final line; preserve it and recover explicitly')
    events, seen = [], set()
    for number, line in enumerate(raw.splitlines(), 1):
        try:
            event = validate(decode(line.decode('utf-8')))
            if event['id'] in seen:
                raise BoardError(f'duplicate event ID: {event["id"]}')
            unknown = set(event.get('refs', [])) - seen
            if unknown:
                raise BoardError(f'references must identify earlier events: {sorted(unknown)}')
        except (BoardError, UnicodeDecodeError) as exc:
            raise BoardError(f'line {number}: {exc}') from exc
        events.append(event)
        seen.add(event['id'])
    return events


def markdown(events):
    chunks = [HEADER]
    for event in events:
        chunks.append(f'\n## {event["ts"]} | {event["agent"]} | {event["type"]} | {event["id"]}\n')
        # Render message text as escaped preformatted data, not active Markdown/HTML.
        lines = []
        for label, key in [('Client', 'client'), ('To', 'to'), ('Scope', 'scope'),
                           ('Message', 'message'), ('Verification', 'verification'),
                           ('Next', 'next'), ('References', 'refs')]:
            value = event.get(key, [])
            if isinstance(value, list):
                value = ', '.join(value) or 'none'
            lines.append(f'{label}: {value}')
        chunks.append('\n<pre>\n' + html.escape('\n'.join(lines)) + '\n</pre>\n')
    return ''.join(chunks)


def render(root, events):
    target = root / 'message-board.md'
    if target.exists() and not target.read_text(encoding='utf-8').startswith(HEADER):
        raise BoardError('existing Markdown is not a generated view; migrate explicitly')
    draft = root / ('.message-board-view-' + uuid.uuid4().hex)
    try:
        with draft.open('x', encoding='utf-8') as handle:
            handle.write(markdown(events))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(draft, target)
    finally:
        draft.unlink(missing_ok=True)


def append(root, events, event, expected):
    head = events[-1]['id'] if events else 'EMPTY'
    if expected != head:
        raise BoardError(f'stale head: expected {expected}, actual {head}; reread and reassess')
    if not isinstance(event, dict):
        raise BoardError('entry must be a JSON object')
    event = dict(event)
    event.setdefault('schema', 1)
    event.setdefault('id', uuid.uuid4().hex)
    event.setdefault('ts', datetime.now(timezone.utc).isoformat())
    event.setdefault('refs', [])
    validate(event)
    seen = {old['id'] for old in events}
    if event['id'] in seen:
        raise BoardError(f'duplicate event ID: {event["id"]}; inspect the existing event')
    if set(event['refs']) - seen:
        raise BoardError('refs must identify earlier events in this log')
    view = root / 'message-board.md'
    if view.exists() and view.read_text(encoding='utf-8') != markdown(events):
        raise BoardError('Markdown view differs from JSONL; inspect and render before appending')
    data = (json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    with (root / 'message-board.jsonl').open('ab') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        render(root, events + [event])
    except (OSError, BoardError) as exc:
        raise BoardError(f'event {event["id"]} IS in JSONL; view refresh failed: {exc}; run render, do not repost') from exc
    return event


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.', help='target worktree or a directory within it')
    commands = parser.add_subparsers(dest='command', required=True)
    status = commands.add_parser('status', help='show log head and events; read before posting')
    status.add_argument('--tail', type=int, help='show only N recent events (not a claims summary)')
    post = commands.add_parser('append', help='append one JSON object supplied by file or stdin')
    post.add_argument('--expect', required=True, help='last event ID you reviewed, or EMPTY')
    post.add_argument('--entry', default='-', help='input JSON file, or - for stdin')
    commands.add_parser('check', help='validate JSONL and exact Markdown correspondence')
    commands.add_parser('render', help='recover the generated Markdown view from valid JSONL')
    args = parser.parse_args(argv)
    try:
        root, lock = location(args.root)
        event = None
        if args.command == 'append':
            # Read stdin before acquiring the lock; never wait on an operator while locked.
            event = decode(sys.stdin.read() if args.entry == '-' else Path(args.entry).read_text(encoding='utf-8'))
        with locked(lock):
            events = read_events(root)
            if args.command == 'append':
                result = append(root, events, event, args.expect)
            elif args.command == 'status':
                if args.tail is not None and args.tail < 1:
                    raise BoardError('--tail must be positive')
                result = {'head': events[-1]['id'] if events else 'EMPTY', 'count': len(events),
                          'events': events[-args.tail:] if args.tail else events}
            else:
                if not (root / 'message-board.jsonl').exists():
                    raise BoardError('no JSONL board exists')
                if args.command == 'render':
                    render(root, events)
                elif not (root / 'message-board.md').exists() or (root / 'message-board.md').read_text(encoding='utf-8') != markdown(events):
                    raise BoardError('Markdown view differs from JSONL; inspect and run render')
                result = {'valid': True, 'count': len(events), 'head': events[-1]['id'] if events else 'EMPTY'}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (BoardError, OSError, UnicodeError) as exc:
        print(f'board: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
