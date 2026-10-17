'use client';

import type { Incident, IncidentAction } from '@hackatl/frontend-transport';
import { useState } from 'react';
import { useProject } from '@/components/project';
import { Async, Button, Empty, Field, inputClass, Mono, Panel, Tag, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { acceptedVerifications, action, closureBlockers, patchEvidence, regressionEvidence, type EvidenceOption } from '@/lib/incidents';
import { useResource } from '@/lib/use-resource';

type Act = (a: IncidentAction) => Promise<boolean>;

const AUDIENCES = ['internal', 'external', 'customer', 'regulator', 'law_enforcement'] as const;
const CSF_COMMS = {
  'RS.CO-02': 'RS.CO-02 · stakeholders notified',
  'RS.CO-03': 'RS.CO-03 · information shared',
  'RC.CO-03': 'RC.CO-03 · recovery communicated',
} as const;

interface ClosureSources { options: EvidenceOption[]; verifications: Array<{ id: string; findingId: string }> }

/** Loads hash-pinned evidence from findings already linked to the incident. */
async function loadSources(findingIds: string[], signal: AbortSignal): Promise<ClosureSources> {
  const options: EvidenceOption[] = [];
  const verifications: ClosureSources['verifications'] = [];
  for (const fid of findingIds) {
    const [patches, detail] = await Promise.all([api().patches(fid, { signal }), api().finding(fid, { signal })]);
    const storedSha: Record<string, string> = {};
    for (const { patch } of patches.items) {
      const art = await api().artifactText(patch.diff_artifact_id, { signal, maxBytes: 2 * 1024 * 1024 });
      storedSha[patch.diff_artifact_id] = art.sha256;
    }
    options.push(...patchEvidence(fid, patches.items, storedSha));
    verifications.push(...acceptedVerifications(patches.items).map(id => ({ id, findingId: fid })));
    for (const r of detail.records) {
      if (r.type !== 'hardening' || !r.record.proposed_test_artifact_id) continue;
      const art = await api().artifactText(r.record.proposed_test_artifact_id, { signal, maxBytes: 512 * 1024 });
      options.push(regressionEvidence(fid, art.id, art.sha256));
    }
  }
  return { options, verifications };
}

/** Linking, closure criteria, lessons learned and communications (NIST SP 800-61r3 RS/RC). */
export function ClosurePanel({ incident, busy, act }: { incident: Incident; busy: boolean; act: Act }) {
  const { project } = useProject();
  const terminal = incident.state === 'closed' || incident.state === 'rejected';
  const findings = useResource(terminal ? null : `findings:${project.id}`, s => api().findings(project.id, { signal: s }));
  const sources = useResource(`closure-sources:${incident.id}:${incident.finding_ids.join(',')}`, s => loadSources(incident.finding_ids, s));
  const blockers = closureBlockers(incident);
  return (
    <Panel title="Closure and evidence" id="closure">
      {!terminal && (
        <section aria-label="Link records" className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">Linked records</h3>
          <Async resource={findings} label="findings">
            {page => <LinkFinding candidates={page.items.filter(f => !incident.finding_ids.includes(f.id)).map(f => ({ id: f.id, label: `${f.title} · ${f.status}` }))} busy={busy} act={act} />}
          </Async>
          <Async resource={sources} label="verifications">
            {src => {
              const open = src.verifications.filter(v => !incident.verification_ids.includes(v.id));
              return src.verifications.length === 0
                ? <p className="text-xs text-muted">No accepted independent verification on the linked findings yet; eradication stays blocked until one is linked.</p>
                : open.length === 0 ? null : <LinkVerification candidates={open} busy={busy} act={act} />;
            }}
          </Async>
        </section>
      )}

      <section aria-label="Closure criteria" className="mt-4 flex flex-col gap-2">
        <h3 className="text-sm font-semibold">Closure criteria</h3>
        {incident.closure_criteria.length === 0 ? <Empty>No closure criteria yet.</Empty> : (
          <ul className="flex flex-col gap-2">
            {incident.closure_criteria.map(c => (
              <li key={c.key} data-testid={`criterion-${c.key}`} className="rounded-md border border-line bg-panel-2 p-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Tag tone={c.satisfied ? 'ok' : 'neutral'}>{c.satisfied ? 'Satisfied' : 'Open'}</Tag>
                  <Mono>{c.key}</Mono><span>{c.description}</span>
                </div>
                {c.satisfied && <div className="mt-1 text-xs text-muted">by <Mono>{c.satisfied_by}</Mono> · {c.evidence.map(e => e.note ?? e.artifact_id ?? e.kind).join(' · ')}</div>}
                {!c.satisfied && !terminal && (
                  <Async resource={sources} label="evidence">
                    {src => <SatisfyCriterion criterionKey={c.key} options={src.options} busy={busy} act={act} />}
                  </Async>
                )}
              </li>
            ))}
          </ul>
        )}
        {!terminal && <AddCriterion busy={busy} act={act} />}
      </section>

      <section aria-label="Lessons learned" className="mt-4 flex flex-col gap-2">
        <h3 className="text-sm font-semibold">Lessons learned</h3>
        {incident.lessons_learned
          ? <p className="text-sm">{incident.lessons_learned} <span className="text-xs text-muted">· {incident.lessons_learned_evidence.length} evidence</span></p>
          : <p className="text-xs text-muted">Not recorded.</p>}
        {incident.state !== 'rejected' && (
          <Async resource={sources} label="regression evidence">
            {src => <RecordLessons options={src.options.filter(o => o.regression)} busy={busy} act={act} />}
          </Async>
        )}
      </section>

      <section aria-label="Communications" className="mt-4 flex flex-col gap-2">
        <h3 className="text-sm font-semibold">Communications</h3>
        {incident.communications.length === 0 ? <p className="text-xs text-muted">None recorded.</p> : (
          <ul className="flex flex-col gap-1 text-sm">
            {incident.communications.map((c, i) => (
              <li key={i}><Tag tone="info">{c.csf_ref}</Tag> {c.audience.replaceAll('_', ' ')} via {c.channel} — {c.summary} <span className="text-xs text-muted">· <Time iso={c.at} /></span></li>
            ))}
          </ul>
        )}
        <RecordCommunication busy={busy} act={act} />
      </section>

      {blockers.length > 0 && (
        <div className="mt-4 rounded-md border border-line bg-panel-2 p-2 text-xs text-muted" aria-label="Closure readiness">
          <p className="font-semibold text-ink">Before closure</p>
          <ul className="list-disc pl-4">{blockers.map(b => <li key={b}>{b}</li>)}</ul>
        </div>
      )}
    </Panel>
  );
}

function LinkFinding({ candidates, busy, act }: { candidates: Array<{ id: string; label: string }>; busy: boolean; act: Act }) {
  const [id, setId] = useState('');
  if (candidates.length === 0) return <p className="text-xs text-muted">Every project finding is already linked (or the project has none).</p>;
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Field label="Finding to link">
        <select className={inputClass} value={id} onChange={e => setId(e.target.value)}>
          <option value="">Choose a finding…</option>
          {candidates.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
      </Field>
      <Button disabled={busy || !id} onClick={async () => { if (await act(action('link', { finding_ids: [id], note: `linked finding ${id}` }))) setId(''); }}>Link finding</Button>
    </div>
  );
}

function LinkVerification({ candidates, busy, act }: { candidates: Array<{ id: string; findingId: string }>; busy: boolean; act: Act }) {
  const [id, setId] = useState(candidates[0]?.id ?? '');
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Field label="Accepted verification to link">
        <select className={inputClass} value={id} onChange={e => setId(e.target.value)}>
          {candidates.map(c => <option key={c.id} value={c.id}>{c.id} · {c.findingId}</option>)}
        </select>
      </Field>
      <Button disabled={busy || !id} onClick={() => act(action('link', { verification_ids: [id], note: `linked independent verification ${id}` }))}>Link verification</Button>
    </div>
  );
}

function AddCriterion({ busy, act }: { busy: boolean; act: Act }) {
  const [key, setKey] = useState('');
  const [desc, setDesc] = useState('');
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Field label="Criterion key"><input className={inputClass} value={key} onChange={e => setKey(e.target.value)} placeholder="regression-green" maxLength={80} /></Field>
      <Field label="Criterion description"><input className={inputClass} value={desc} onChange={e => setDesc(e.target.value)} placeholder="Regression suite passes on the fix" maxLength={300} /></Field>
      <Button disabled={busy || !key.trim() || !desc.trim()} onClick={async () => {
        if (await act(action('add_closure_criterion', { criterion_key: key.trim(), note: desc.trim() }))) { setKey(''); setDesc(''); }
      }}>Add criterion</Button>
    </div>
  );
}

function SatisfyCriterion({ criterionKey, options, busy, act }: { criterionKey: string; options: EvidenceOption[]; busy: boolean; act: Act }) {
  const [pick, setPick] = useState(options[0]?.key ?? '');
  if (options.length === 0) return <p className="mt-1 text-xs text-muted">Link a finding with a persisted patch or regression artifact to satisfy this with evidence.</p>;
  const chosen = options.find(o => o.key === pick);
  return (
    <div className="mt-2 flex flex-wrap items-end gap-2">
      <Field label={`Evidence for ${criterionKey}`}>
        <select className={inputClass} value={pick} onChange={e => setPick(e.target.value)}>
          {options.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
        </select>
      </Field>
      <Button disabled={busy || !chosen} onClick={() => chosen && act(action('satisfy_closure_criterion', { criterion_key: criterionKey, evidence: [chosen.ref], note: `${criterionKey} satisfied` }))}>Mark satisfied</Button>
    </div>
  );
}

function RecordLessons({ options, busy, act }: { options: EvidenceOption[]; busy: boolean; act: Act }) {
  const [text, setText] = useState('');
  const [pick, setPick] = useState(options[0]?.key ?? '');
  if (options.length === 0) {
    return <p className="text-xs text-muted">No Fortify regression-test artifact is recorded on the linked findings. Lessons learned must cite one, so the backend will refuse closure until it exists.</p>;
  }
  const chosen = options.find(o => o.key === pick);
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Field label="Lessons learned"><input className={inputClass} value={text} onChange={e => setText(e.target.value)} maxLength={500} /></Field>
      <Field label="Regression evidence">
        <select className={inputClass} value={pick} onChange={e => setPick(e.target.value)}>
          {options.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
        </select>
      </Field>
      <Button disabled={busy || !text.trim() || !chosen} onClick={async () => {
        if (chosen && await act(action('record_lessons_learned', { note: text.trim(), evidence: [chosen.ref] }))) setText('');
      }}>Record lessons</Button>
    </div>
  );
}

function RecordCommunication({ busy, act }: { busy: boolean; act: Act }) {
  const [audience, setAudience] = useState<(typeof AUDIENCES)[number]>('internal');
  const [channel, setChannel] = useState('');
  const [csf, setCsf] = useState<keyof typeof CSF_COMMS>('RS.CO-02');
  const [summary, setSummary] = useState('');
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Field label="Audience">
        <select className={inputClass} value={audience} onChange={e => setAudience(e.target.value as (typeof AUDIENCES)[number])}>
          {AUDIENCES.map(a => <option key={a} value={a}>{a.replaceAll('_', ' ')}</option>)}
        </select>
      </Field>
      <Field label="Channel"><input className={inputClass} value={channel} onChange={e => setChannel(e.target.value)} placeholder="#sec-incidents" maxLength={100} /></Field>
      <Field label="CSF outcome">
        <select className={inputClass} value={csf} onChange={e => setCsf(e.target.value as keyof typeof CSF_COMMS)}>
          {Object.entries(CSF_COMMS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </Field>
      <Field label="Summary"><input className={inputClass} value={summary} onChange={e => setSummary(e.target.value)} maxLength={500} /></Field>
      <Button disabled={busy || !channel.trim() || !summary.trim()} onClick={async () => {
        if (await act(action('record_communication', { audience, channel: channel.trim(), csf_ref: csf, note: summary.trim() }))) { setChannel(''); setSummary(''); }
      }}>Record communication</Button>
    </div>
  );
}
