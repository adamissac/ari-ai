export const RECORDED_LIVE_RUN = {
  assessmentId: 'asm_01M55T1G74F5RQERH65HWCQB1H',
  recordedAt: '2026-10-17T20:53Z',
  commit: 'b44d372',
  model: 'claude-opus-5-5',
  target: 'examples/payments-lite (owned fixture, local sandbox)',
  durationSeconds: 225,
  usd: 1.3863,
  capUsd: 6,
  states: [
    'scope_check', 'indexing', 'functional_review', 'recon', 'validation', 'analysis',
    'diagnosis', 'awaiting_approval', 'remediation', 'hardening', 'reporting', 'completed',
  ],
  agents: [
    { agent: 'Scout', status: 'succeeded', turns: 4, tools: 8, usd: 0.188 },
    { agent: 'Probe', status: 'succeeded', turns: 3, tools: 4, usd: 0.0832 },
    { agent: 'Trace', status: 'succeeded', turns: 4, tools: 6, usd: 0.2275 },
    { agent: 'Diagnose', status: 'succeeded', turns: 3, tools: 4, usd: 0.1472 },
    { agent: 'Patch', status: 'succeeded', turns: 5, tools: 9, usd: 0.3117 },
    { agent: 'Verify', status: 'succeeded', turns: 5, tools: 6, usd: 0.137 },
    { agent: 'Fortify', status: 'succeeded', turns: 4, tools: 7, usd: 0.2916 },
  ],
  findings: [
    {
      title: "GET /payments/{payment_id} may return any customer's payment: there is no require_owner check",
      cwe: 'CWE-639',
      outcome: 'Probe confirmed it (ownership check on payment_detail failed); Patch fixed it; Verify accepted; Fortify hardened it',
      regressionTest: 'tests/test_payment_ownership.py',
    },
    {
      title: 'POST /refunds only checks each refund against the payment amount, not the running total',
      cwe: 'CWE-841',
      outcome: 'Hypothesis only: this run validates one hypothesis, so it was not checked',
      regressionTest: null,
    },
  ],
  limitations: [
    'One run on one owned fixture',
    'Local-process sandbox, not Docker',
    'Remediation approved automatically by the CLI, not by a person',
    'The new regression test was not run on the unpatched snapshot; this recording does not establish red-to-green proof',
  ],
} as const;
