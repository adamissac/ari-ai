import assert from 'node:assert/strict';
import { test } from 'node:test';
import { findingStandards, incidentLabel, mappingLabel } from '../dist/frontend/transport/src/standards.js';

test('missing severity is explicitly unscored and simulation remains visible', () => {
  assert.equal(findingStandards({ standards: null }).cvss, 'Not assessed');
  const value = findingStandards({ standards: { cwe: null, attack: [], d3fend: [], cvss: { complete: false, missing_metrics: ['AV', 'VI'], assumptions: [] }, unmapped: ['No official relation'] } });
  assert.equal(value.cvss, 'Unscored · missing AV, VI');
  assert.deepEqual(value.limitations, ['No official relation']);
  assert.match(incidentLabel({ title: 'Demo', simulated: true, state: 'reported', csf_function: 'DE' }), /^Simulated/);
});

test('scored vectors, versions, observation and review status stay visible', () => {
  assert.match(mappingLabel({ id: 'T1190', name: 'Exploit Public-Facing Application', catalog_version: '20.0', observation: 'hypothesis', review_status: 'proposed' }), /20\.0.*hypothesis.*proposed/);
  const value = findingStandards({ standards: { cwe: null, attack: [], d3fend: [], cvss: { version: '4.0', complete: true, score: 9.3, severity: 'critical', vector: 'CVSS:4.0/...', assumptions: ['Human assessed'] }, unmapped: [] } });
  assert.match(value.cvss, /9\.3.*CVSS:4\.0/);
  assert.deepEqual(value.limitations, ['Human assessed']);
});
