"""Read-only candidate/landing audit; original assertions remain strict."""
import json
import os
import subprocess
from pathlib import Path
from scripts.ari_review import ci

original_git, original_command = ci.git, ci.test_command
candidate = Path('../candidate').resolve()
directory = Path(os.environ['RUNNER_TEMP']) / 'b6d-evidence'
pin = json.loads((directory / 'pin.json').read_text())
pin['production_candidate_sha'] = pin['candidate_sha']
if os.environ['AUDIT_MODE'] == 'landing':
    original_git('fetch', '--no-tags', 'https://github.com/adamissac/ari-ai.git', pin['upstream_sha'], cwd=candidate)
    merged = original_git('merge-tree','--write-tree',pin['upstream_sha'],pin['candidate_sha'],cwd=candidate,check=False)
    tree = merged.stdout.splitlines()[0]
    if merged.returncode:
        conflicts = [line for line in merged.stdout.splitlines() if line.startswith('CONFLICT')]
        assert conflicts == ['CONFLICT (content): Merge conflict in docs/planning/SESSION_HANDOFF.md'], conflicts
        # Explicit review-only documentary resolution; never resolve product code.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='rc5-index-') as scratch:
            index_env = dict(os.environ,GIT_INDEX_FILE=str(Path(scratch)/'index'))
            def index(*args):
                return subprocess.run(['git',*args],cwd=candidate,env=index_env,text=True,capture_output=True,check=True).stdout.strip()
            index('read-tree',tree)
            blob = original_git('rev-parse',pin['upstream_sha']+':docs/planning/SESSION_HANDOFF.md',cwd=candidate).stdout.strip()
            index('update-index','--cacheinfo','100644,'+blob+',docs/planning/SESSION_HANDOFF.md')
            tree = index('write-tree')
        pin['review_only_doc_resolution'] = 'SESSION_HANDOFF.md selected from current main; no product conflict resolved'

    stamp = original_git('show', '-s', '--format=%cI', pin['upstream_sha'], cwd=candidate).stdout.strip()
    env = dict(os.environ, GIT_AUTHOR_NAME='Independent review', GIT_COMMITTER_NAME='Independent review', GIT_AUTHOR_EMAIL='review@localhost', GIT_COMMITTER_EMAIL='review@localhost', GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
    commit = subprocess.run(['git','commit-tree',tree,'-p',pin['upstream_sha'],'-p',pin['candidate_sha']],input='Review-only RC5 current-main landing simulation\n',cwd=candidate,text=True,capture_output=True,check=True,env=env).stdout.strip()
    landing = candidate.parent / 'landing'
    original_git('clone','--no-hardlinks','--no-checkout',str(candidate),str(landing),cwd=candidate)
    original_git('checkout','--detach',commit,cwd=landing)
    candidate = landing
    pin['candidate_sha'] = commit
    pin['landing_tree'] = tree
(directory / 'pin.json').write_text(json.dumps(pin,indent=2)+'\n')
extra = Path('docs/reviews/b6d5108b-independent/test_additional.py').resolve()
def git(*args, **kwargs):
    result = original_git(*args, **kwargs)
    if args[:2] == ('worktree','add'):
        target = Path(args[3])
        if target.name == 'independent-suite':
            (target/'test-results').mkdir(exist_ok=True)
            (target/'backend/tests/test_rc5_additional.py').write_bytes(extra.read_bytes())
            path = target/'backend/tests/test_customer_security_hardening.py'
            source = path.read_text()
            old = 'settings_override(rate_limit_per_minute="3")'
            assert source.count(old) == 1
            path.write_text(source.replace(old,'settings_override(rate_limit_read_per_minute="3")'))
    return result
results = None
def command(network,candidate,suite,evidence,config,tests):
    global results
    results = evidence.resolve()
    tests = list(tests) + ['/suite/security-agents/tests/test_ari_latest_protected.py::'+name for name in [
      'test_imported_pytest_hook_code_replacement_is_flagged',
      'test_rootdir_symlinked_pyproject_checks_resolved_target',
      'test_root_conftest_is_flagged_when_section_checked_config_is_symlink_target']]
    args = original_command(network,candidate,suite,evidence,config,tests)
    index = args.index('ari-review-tests')
    args[index:index] = ['--mount',f'type=bind,src={results},dst=/suite/test-results']
    return args
# Restore removal permission on container-owned result directories after all
# test containers stop. Same unprivileged uid, only the results mount, no network,
# no symlink following or host paths/credentials. Never rewrites test results.
class Docker(ci.Docker):
    def call(self,*args,**kwargs):
        if args[:2] == ('network','rm') and results is not None:
            code = "import os; from pathlib import Path; root=Path('/evidence');\nfor p,ds,fs in os.walk(root,followlinks=False):\n for d in ds:\n  q=Path(p)/d\n  if not q.is_symlink(): q.chmod(q.stat().st_mode|0o777)"
            super().call('run','--rm','--network','none','--read-only','--user','10001:10001','--cap-drop=ALL','--security-opt=no-new-privileges','--mount',f'type=bind,src={results},dst=/evidence','ari-review-tests','/app/.venv/bin/python','-c',code,check=False,capture_output=True)
        return super().call(*args,**kwargs)
ci.git,ci.test_command,ci.Docker = git,command,Docker
policy = json.loads(Path('.github/ari-review/policy.json').read_text())
policy['regressions'].append('backend/tests/test_rc5_additional.py')
raise SystemExit(ci.run(candidate,directory.resolve(),policy))
