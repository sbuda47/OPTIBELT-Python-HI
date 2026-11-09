"""Audit Git's proposed/tracked content, without scanning excluded private data.

This is a release hygiene check, not a guarantee that every secret or rights
issue can be detected automatically. It inspects the index (the next commit).
"""
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def main():
    entries = git('ls-files', '--stage', '-z').split(b'\0')
    failures = []
    count = total = 0
    private_parts = {'node_modules', '__pycache__', '.venv', '.venv-web',
                     '.aws', '.codex', 'private', 'verification'}
    private_prefixes = ('dataset/raw/', 'dataset/processed/', 'outputs/runs/',
                        'outputs/live_sessions/', 'visualizations/')
    private_suffixes = {'.mat', '.npz', '.h5', '.tdms', '.zip', '.pdf',
                        '.pem', '.key', '.log', '.pyc'}
    # Match high-confidence credential formats, without printing their values.
    patterns = [re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
                re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
                re.compile(rb'AKIA[0-9A-Z]{16}'),
                re.compile(rb'[A-Za-z]:[/\\]Users[/\\][^/\\\s]+', re.I)]
    for entry in entries:
        if not entry:
            continue
        metadata, raw_path = entry.split(b'\t', 1)
        mode, oid, stage = metadata.split()
        name = raw_path.decode('utf-8')
        p = PurePosixPath(name)
        if stage != b'0' or mode not in (b'100644', b'100755'):
            failures.append((name, 'unmerged, symlink, or non-regular entry'))
            continue
        if (private_parts.intersection(p.parts) or name.startswith(private_prefixes)
                or p.suffix.lower() in private_suffixes
                or re.fullmatch(r'\.z\d\d', p.suffix.lower())
                or p.name.startswith('.env') and p.name != '.env.example'):
            failures.append((name, 'private, generated, or raw-data file'))
        data = git('cat-file', 'blob', oid.decode())
        count += 1
        total += len(data)
        if len(data) > 10 * 1024 * 1024:
            failures.append((name, 'file exceeds 10 MiB review limit'))
        if b'\0' not in data[:8192] and any(pattern.search(data) for pattern in patterns):
            failures.append((name, 'possible credential or personal absolute path'))
    if not count:
        failures.append(('<index>', 'no staged/tracked files; run git add first'))
    for name, reason in failures:
        print(f'FAIL: {name}: {reason}')
    print(f'{"FAIL" if failures else "PASS"}: {count} Git files, {total:,} bytes; '
          f'{len(failures)} content-audit findings.')
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
