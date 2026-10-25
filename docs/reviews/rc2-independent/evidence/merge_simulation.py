"""Reproduce the recorded read-only transfer squash simulation.

Writes only unreferenced Git objects. Never updates a ref, HEAD or worktree.
Stops at the first non-documentation conflict. Fetch pinned inputs first.
"""
import json
import os
import subprocess

BASE = '4d4be9e395bfe6ab59b62962b688570e2d2d5261'
INPUTS = [
    ('upstream412', '4ecd7558c20d676985294073d5a818a538bdf78c'),
    ('upstream458', '8396e836866e33ebc34a402a7c8bd0eb6bc769d8'),
    ('reliability', 'ae414985d09796cc950b7e833157861d239abc29'),
    ('observability', '9fc0429a71781a53815982b1c9426c9330989506'),
    ('hardening', 'a68817fbda7e37e8cd0fd597458d8c606015e0d9'),
    ('onboarding', 'a217d3c984138cdaf6ef4ee238234e4fba7fbe17'),
    ('ops', 'c7c5336f79a9172b27e03d9570e7ae708b1f78b1'),
    ('validation', '7ba1ab7707d52716dcae118de0f78b805ac15fde'),
]
steps = []
for label, incoming in INPUTS:
    result = subprocess.run(['git', 'merge-tree', '--write-tree', '--messages', BASE, incoming], capture_output=True, text=True)
    lines = result.stdout.splitlines()
    tree = lines[0] if lines else None
    conflicts = sorted({line.split('\t', 1)[1] for line in lines if '\t' in line and line[:6].isdigit()})
    steps.append({'label': label, 'base': BASE, 'incoming': incoming, 'exit': result.returncode, 'tree': tree, 'conflicts': conflicts, 'output': result.stdout, 'stderr': result.stderr})
    production = [path for path in conflicts if not (path.endswith('.md') or path.startswith('coordination/'))]
    if result.returncode not in (0, 1) or production:
        break
    env = dict(os.environ, GIT_AUTHOR_NAME='Independent audit simulation', GIT_AUTHOR_EMAIL='audit@example.invalid', GIT_COMMITTER_NAME='Independent audit simulation', GIT_COMMITTER_EMAIL='audit@example.invalid')
    BASE = subprocess.check_output(['git', 'commit-tree', tree, '-p', BASE, '-m', 'Unreferenced audit-only squash simulation'], env=env, text=True).strip()
print(json.dumps(steps, indent=2))
