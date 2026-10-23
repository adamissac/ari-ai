'use client';

import type { ConnectedApplication, DefenseHealth, IngestTokenCreated, IngestTokenView } from '@hackatl/frontend-transport';
import { useState } from 'react';
import { ShadowModeNote, SourceTag } from '@/components/live-defense/common';
import { Async, Button, Empty, ErrorState, Field, inputClass, Mono, Panel, Tag, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { ingestCurl, type LiveDefenseMode } from '@/lib/live-defense';
import type { Resource } from '@/lib/use-resource';

export function StagingApps({
  mode,
  projectId,
  apps,
  tokens,
  health,
  onChange,
}: {
  mode: LiveDefenseMode;
  projectId: string | null;
  apps?: Resource<{ items: ConnectedApplication[] }>;
  tokens?: Resource<{ items: IngestTokenView[] }>;
  health?: Resource<DefenseHealth>;
  onChange?: () => void;
}) {
  if (mode === 'layout-preview') {
    return (
      <Panel title="Sample staging-app chrome" actions={<SourceTag mode="layout-preview" />}>
        <p className="text-sm text-ink">Sample layout only. No app is registered and no ingest token is issued here.</p>
      </Panel>
    );
  }
  if (!projectId) return <Empty>Choose a project to register a staging app.</Empty>;
  return (
    <div className="flex flex-col gap-4" data-testid="live-defense-apps">
      <ShadowModeNote />
      <RegisterApp projectId={projectId} onChange={onChange} />
      <Panel title="Registered staging apps" actions={<SourceTag mode="live" />}>
        {apps ? (
          <Async resource={apps} label="staging apps">
            {page => page.items.length === 0 ? (
              <Empty>No staging app yet. Only sandbox and owned-test environments are allowed. Production enforcement grants are not offered.</Empty>
            ) : (
              <ul className="flex flex-col gap-3">
                {page.items.map(app => (
                  <AppCard key={app.id} app={app} projectId={projectId} tokens={tokens} onChange={onChange} />
                ))}
              </ul>
            )}
          </Async>
        ) : <Empty>Apps were not requested.</Empty>}
      </Panel>
      <Panel title="Ingest guidance">
        <p className="text-sm text-ink">Send aggregated per-route counters to the existing ingest endpoint. Never put raw logs, payloads, or secrets in the batch.</p>
        <pre className="mt-3 overflow-x-auto rounded-md border border-line bg-panel-2 p-3 text-xs text-ink">{ingestCurl(projectId)}</pre>
        <p className="mt-2 text-xs text-muted">The token is shown once at issuance. Later lists return metadata only (id, last used, revoked). Owners revoke from this page.</p>
        {health ? (
          <Async resource={health} label="ingest health">
            {item => (
              <p className="mt-3 text-sm text-ink">
                Last ingest window: {item.last_ingest_at ? <Time iso={item.last_ingest_at} /> : 'unavailable'}.
                Status remains <strong>{item.status}</strong> — {item.status_reason}
              </p>
            )}
          </Async>
        ) : null}
      </Panel>
    </div>
  );
}

function RegisterApp({ projectId, onChange }: { projectId: string; onChange?: () => void }) {
  const [name, setName] = useState('');
  const [environment, setEnvironment] = useState<'sandbox' | 'owned_test'>('sandbox');
  const [status, setStatus] = useState<'idle' | 'saving' | 'error'>('idle');
  const [error, setError] = useState<unknown>(null);
  const submit = async () => {
    setStatus('saving');
    setError(null);
    try {
      await api().createConnectedApplication(projectId, { name: name.trim(), environment });
      setName('');
      setStatus('idle');
      onChange?.();
    } catch (err) {
      setError(err);
      setStatus('error');
    }
  };
  return (
    <Panel title="Register an authorized staging app">
      <p className="mb-3 text-sm text-muted">Identity and environment class only. Ari will not grant production enforcement from this form.</p>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <Field label="Name">
          <input className={inputClass} value={name} onChange={e => setName(e.target.value)} maxLength={500} required />
        </Field>
        <Field label="Environment">
          <select className={inputClass} value={environment} onChange={e => setEnvironment(e.target.value as 'sandbox' | 'owned_test')}>
            <option value="sandbox">sandbox</option>
            <option value="owned_test">owned test</option>
          </select>
        </Field>
        <Button variant="primary" disabled={status === 'saving' || name.trim().length === 0} onClick={() => void submit()}>Register app</Button>
      </div>
      {status === 'error' && error !== null && <div className="mt-2"><ErrorState error={error} onRetry={() => void submit()} context="Register app" /></div>}
    </Panel>
  );
}

function AppCard({
  app,
  projectId,
  tokens,
  onChange,
}: {
  app: ConnectedApplication;
  projectId: string;
  tokens?: Resource<{ items: IngestTokenView[] }>;
  onChange?: () => void;
}) {
  const [issued, setIssued] = useState<IngestTokenCreated | null>(null);
  const [error, setError] = useState<unknown>(null);
  const mint = async () => {
    setError(null);
    try {
      setIssued(await api().createApplicationIngestToken(app.id));
      onChange?.();
    } catch (err) {
      setError(err);
    }
  };
  const appTokens = tokens?.status === 'ready' ? tokens.data.items.filter(item => item.application_id === app.id) : [];
  return (
    <li className="rounded-md border border-line bg-panel-2 p-3 text-sm text-ink" data-testid={`live-defense-app-${app.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium">{app.name}</p>
        <span className="flex flex-wrap gap-1">
          <Tag>{app.environment.replaceAll('_', ' ')}</Tag>
          <Tag tone="info">shadow mode</Tag>
          <Tag>{app.verification.replaceAll('_', ' ')}</Tag>
        </span>
      </div>
      <p className="mt-1 text-xs text-muted">
        Ingest configured: {app.ingest_configured ? 'yes' : 'no'} · last seen {app.last_ingest_at ? <Time iso={app.last_ingest_at} /> : 'unavailable'}
      </p>
      <p className="mt-2 text-xs text-muted">POST {`/api/v1/ingest/runtime/${projectId}`} with Bearer token. Token secret is not stored in recoverable form.</p>
      <Button className="mt-3 !px-2 !py-0.5 text-xs" onClick={() => void mint()}>Issue ingest token</Button>
      {error !== null && <div className="mt-2"><ErrorState error={error} /></div>}
      {issued && (
        <div className="mt-3 rounded-md border border-warn/50 bg-warn/10 p-2 text-xs" data-testid="live-defense-token-once">
          <p className="font-medium text-warn">Copy this token now. Ari will not show it again.</p>
          <Mono className="mt-1 block break-all text-ink">{issued.token}</Mono>
        </div>
      )}
      {appTokens.length > 0 && (
        <ul className="mt-3 text-xs text-muted">
          {appTokens.map(token => (
            <li key={token.id} className="flex flex-wrap items-center gap-2 py-1">
              <Mono>{token.id}</Mono>
              {token.revoked_at ? <Tag tone="warn">revoked</Tag> : <Tag tone="ok">active</Tag>}
              last used {token.last_used_at ? <Time iso={token.last_used_at} /> : 'unavailable'}
              {!token.revoked_at && (
                <Button className="!h-6 !px-2 !py-0 text-[11px]" onClick={() => { void api().revokeIngestToken(token.id).then(() => onChange?.()); }}>
                  Revoke
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
