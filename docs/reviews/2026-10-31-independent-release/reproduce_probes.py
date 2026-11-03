"""Read exact Git objects; use synthetic canaries and mocked GitHub, never the network."""
from pathlib import Path
import json
import subprocess
from types import SimpleNamespace

MAIN = '9437e217d65aa1be22fa7b4f54f723200cd428c8'
FIX = '72753087abef39a84103fe9fbcf43248430a7ebb'
ROOT = Path(__file__).resolve().parents[3]

def load(sha, path):
    source = subprocess.check_output(['git', 'show', f'{sha}:{path}'], cwd=ROOT, text=True)
    scope = {'__file__': str(ROOT / path), '__name__': 'independent_probe'}
    exec(compile(source, path, 'exec'), scope)
    return scope

for sha in (MAIN, FIX):
    redact = load(sha, 'backend/backend/redaction.py')['redact_code']
    for path, line in (
        ('app/settings.py', 'password = r"synthetic-audit-canary"'),
        ('app/settings.py', 'token = """synthetic-audit-canary"""'),
        ('deploy/values.yaml', '  password: synthetic-audit-canary'),
    ):
        diff = f'diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1 @@\n+{line}\n'
        exposed = 'synthetic-audit-canary' in redact(diff)
        assert exposed == (sha == MAIN)
        print(json.dumps({'sha': sha, 'path': path, 'credential_exposed': exposed}))

checker = load(MAIN, 'deploy/release_check.py')
real_run = subprocess.run
try:
    for checks in ([], [{'name': 'backend-tests', 'status': 'COMPLETED', 'conclusion': 'SKIPPED'}]):
        subprocess.run = lambda *_args, **_kw: SimpleNamespace(
            returncode=0, stdout=json.dumps({'statusCheckRollup': checks, 'number': 1}), stderr=''
        )
        checker['results'].clear()
        checker['check_ci']()
        assert checker['results'][0][0] == 'PASS'
finally:
    subprocess.run = real_run
