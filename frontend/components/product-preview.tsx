/** The landing hero's product view: the commit stream on main, as the console shows it. Sample data. */
const STREAM = [
  { sha: '9e41c07', msg: 'feat(transfers): allow scheduled transfers', state: 'running', note: 'Security agents testing 3 suspicions' },
  { sha: '3f2a9c1', msg: 'feat(payments): add GET /transfers/{id}', state: 'fixed', note: 'Ownership bypass confirmed, fix verified' },
  { sha: 'b7d2e88', msg: 'refactor(ledger): split balance helpers', state: 'clean', note: 'Reviewed and attacked, nothing found' },
  { sha: '51ac0f3', msg: 'chore(deps): bump fastapi to 0.115.4', state: 'clean', note: 'Reviewed and attacked, nothing found' },
] as const;

const STAGES = ['Review', 'Attack', 'Fix', 'Verify', 'Commit'];

export function ProductPreview() {
  return (
    <figure className="pv" aria-label="Sample of Ari reviewing the commits on a repository's main branch">
      <div className="pv-bar">
        <span><b>lumen-pay/payments-api</b> · main</span>
        <span className="pv-live"><i aria-hidden="true" />Watching every push</span>
      </div>
      <ol className="pv-stream">
        {STREAM.map(c => (
          <li key={c.sha} data-state={c.state}>
            <span className="pv-sha font-mono">{c.sha}</span>
            <span className="pv-msg">{c.msg}<small>{c.note}</small></span>
            <span className="pv-state">{c.state === 'running' ? 'Testing' : c.state === 'fixed' ? 'Fixed' : 'Clean'}</span>
          </li>
        ))}
      </ol>
      <div className="pv-body">
        <div className="pv-rail" aria-label="Steps for commit 3f2a9c1">
          {STAGES.map(s => <span key={s}>{s}</span>)}
        </div>
        <p className="pv-title">GET /transfers/&#123;id&#125; returned another customer&apos;s transfer</p>
        <div className="pv-diff" aria-label="Fix Ari committed">
          <div className="pv-del">{'- return transfer'}</div>
          <div className="pv-add">{'+ if transfer.owner_id != user.id:'}</div>
          <div className="pv-add">{'+     raise HTTPException(status_code=404)'}</div>
          <div className="pv-add">{'+ return transfer'}</div>
        </div>
        <p className="mt-3 flex flex-wrap gap-2">
          <span className="evidence-tag">test_cross_owner_read_denied: fails before, passes after</span>
        </p>
      </div>
      <figcaption className="pv-foot">
        <span className="pv-ok">Committed to main as c18e4a0 by ari-security[bot]</span>
      </figcaption>
    </figure>
  );
}
