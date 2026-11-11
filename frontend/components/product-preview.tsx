/** The landing hero's product view: one reviewed commit, as the console shows it. Sample data. */
export function ProductPreview() {
  return (
    <figure className="pv" aria-label="Sample of an Ari review of one commit">
      <div className="pv-bar">
        <span><b>lumen-pay/payments-api</b> · main</span>
        <span className="font-mono">3f2a9c1</span>
      </div>
      <div className="pv-steps">
        {['Review', 'Attack in sandbox', 'Diagnose', 'Fix', 'Verify'].map(step => <span key={step}>{step}</span>)}
      </div>
      <div className="pv-body">
        <p className="pv-title">GET /transfers/&#123;id&#125; returns another customer&apos;s transfer</p>
        <p className="pv-meta"><span className="pv-high">High</span><span>Confirmed by a test</span><span className="font-mono">payments/routes.py:88</span></p>
        <div className="pv-diff" aria-label="Proposed fix">
          <div>{'  transfer = store.get_transfer(transfer_id)'}</div>
          <div className="pv-del">{'- return transfer'}</div>
          <div className="pv-add">{'+ if transfer.owner_id != user.id:'}</div>
          <div className="pv-add">{'+     raise HTTPException(status_code=404)'}</div>
          <div className="pv-add">{'+ return transfer'}</div>
        </div>
        <p className="mt-3 flex flex-wrap gap-2">
          <span className="evidence-tag">test_cross_owner_read_denied</span>
          <span className="evidence-tag">42 existing tests</span>
        </p>
      </div>
      <figcaption className="pv-foot">
        <span className="pv-ok">Fix verified by independent tests</span>
        <span className="text-muted">Pull request ready for your review</span>
      </figcaption>
    </figure>
  );
}
