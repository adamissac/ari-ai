"""Review-only harness: writable result mount; independent assertions unchanged."""
import json
import os
from pathlib import Path
from scripts.ari_review import ci
original_git, original_command = ci.git, ci.test_command
extra = Path('docs/reviews/rc4-n8-independent/test_additional.py').resolve()
def git(*args, **kwargs):
    result = original_git(*args, **kwargs)
    if args[:2] == ('worktree', 'add'):
        target = Path(args[3])
        if target.name == 'independent-suite':
            (target / 'test-results').mkdir(exist_ok=True)
            (target / 'backend/tests/test_rc4_additional.py').write_bytes(extra.read_bytes())
    return result
def command(network, candidate, suite, evidence, config, tests):
    result = original_command(network, candidate, suite, evidence, config, tests)
    index = result.index('ari-review-tests')
    result[index:index] = ['--mount', f'type=bind,src={evidence.resolve()},dst=/suite/test-results']
    return result
ci.git, ci.test_command = git, command
policy = json.loads(Path('.github/ari-review/policy.json').read_text())
policy['regressions'].append('backend/tests/test_rc4_additional.py')
raise SystemExit(ci.run(Path('../candidate').resolve(), Path(os.environ['RUNNER_TEMP']+'/rc4-evidence').resolve(), policy))
