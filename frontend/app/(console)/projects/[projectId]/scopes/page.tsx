'use client';

import type { AuthorizedScope, CheckCategory } from '@hackatl/frontend-transport';
import { useState, type FormEvent } from 'react';
import { useProject } from '@/components/project';
import { Term } from '@/components/term';
import { useSession } from '@/components/session';
import { Async, Badge, Button, Empty, ErrorState, Field, inputClass, Mono, PageTitle, Panel, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { useActionKeys } from '@/lib/action-key';
import { REQUEST_SCOPE_NOTE, SCOPE_CHECK_CATEGORIES, SCOPE_SANDBOX_EXPLANATION } from '@/lib/scope';
import { isSandboxOnlyScope, scopeBody } from '@/lib/real-assessment';
import { effectiveScopeStatus, SCOPE_STATUS } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

export default function ScopesPage() {
  const { project, selectedRepo } = useProject();
  const scopes = useResource(`scopes:${project.id}`, s => api().scopes(project.id, { signal: s }));
  return (
    <div className="flex min-w-0 flex-col gap-6">
      <PageTitle eyebrow="Defend" title="Authorized scopes" subtitle={selectedRepo
        ? <>Approved sandbox targets for <span className="font-mono text-ink">{selectedRepo.full_name}</span>.</>
        : 'Select a connected repository to review its authorized sandbox targets.'} />
      <p className="text-sm text-muted" data-testid="scope-sandbox-explanation">{SCOPE_SANDBOX_EXPLANATION}</p>
      <div className="grid min-w-0 grid-cols-1 gap-6 xl:grid-cols-[3fr_2fr]">
      <Panel title="Authorized test scopes">
        <p className="mb-3 text-sm text-muted">
          A <Term t="scope">scope</Term> lists the only <Term t="sandbox">sandbox</Term> targets agents may build and test, and the only check categories Probe may run. It becomes
          active after a project owner explicitly approves it. Owners may approve their own sandbox-only scopes; other scopes require a different owner. The backend enforces this.
        </p>
        <Async resource={scopes} label="scopes">
          {page => {
            const items = page.items.flatMap(scope => {
              const targets = selectedRepo ? scope.targets.filter(target => target.repo_id === selectedRepo.id) : [];
              return targets.length > 0 ? [{ scope, targets }] : [];
            });
            return items.length === 0 ? <Empty>{selectedRepo ? 'No scopes target this repository.' : 'Connect a repository first.'}</Empty> : (
              <ul className="divide-y divide-line">{items.map(({ scope, targets }) => <ScopeRow key={scope.id} scope={scope} targets={targets} repoName={selectedRepo!.full_name} onChange={scopes.reload} />)}</ul>
            );
          }}
        </Async>
      </Panel>
      <RequestScope onCreated={scopes.reload} />
    </div>
    </div>
  );
}

function ScopeRow({ scope, targets, repoName, onChange }: { scope: AuthorizedScope; targets: AuthorizedScope['targets']; repoName: string; onChange: () => void }) {
  const { me } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try { await fn(); onChange(); } catch (err) { setError(err); } finally { setBusy(false); }
  };
  const mine = scope.requested_by === me.user.id;
  const needsOtherOwner = mine && !isSandboxOnlyScope(scope);
  const status = effectiveScopeStatus(scope);
  return (
    <li className="py-4 first:pt-0 last:pb-0" data-testid={`scope-${scope.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="min-w-0 break-words font-medium">{scope.name}</span>
        <Badge view={SCOPE_STATUS[status]} />
      </div>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs text-muted">
        <dt>Targets</dt>
        <dd>{targets.map(t => <div key={t.repo_id + t.build_recipe_ref}>{repoName} · sandbox build from <Mono>{t.build_recipe_ref}</Mono>{t.exposed_ports.length > 0 && <> · ports {t.exposed_ports.join(', ')}</>}</div>)}</dd>
        <dt>Checks</dt><dd>{scope.allowed_check_categories.join(', ') || 'none'}</dd>
        <dt>Requested by</dt><dd><Mono>{scope.requested_by}</Mono>{mine && ' (you)'}</dd>
        <dt>Approved</dt><dd>{scope.approved_by ? <><Mono>{scope.approved_by}</Mono> · <Time iso={scope.approved_at} /></> : '—'}</dd>
        <dt>Expires</dt><dd><Time iso={scope.expires_at} /></dd>
        {scope.notes && <><dt>Notes</dt><dd>{scope.notes}</dd></>}
      </dl>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {status === 'pending' && (
          <Button variant="primary" disabled={busy || needsOtherOwner} onClick={() => act(() => api().approveScope(scope.id))} title={needsOtherOwner ? 'This scope requires a different owner' : undefined}>
            Approve scope
          </Button>
        )}
        {(status === 'pending' || status === 'active') && (
          <Button variant="danger" disabled={busy} onClick={() => act(() => api().revokeScope(scope.id))}>Revoke</Button>
        )}
        {status === 'pending' && needsOtherOwner && <span className="text-xs text-warn">Waiting for another member to approve.</span>}
      </div>
      {error !== null && <div className="mt-2"><ErrorState error={error} context="Scope action failed" /></div>}
    </li>
  );
}

function RequestScope({ onCreated }: { onCreated: () => void }) {
  const { project, selectedRepo } = useProject();
  const [name, setName] = useState('');
  const [recipe, setRecipe] = useState('build_recipe.json');
  const [categories, setCategories] = useState<CheckCategory[]>([...SCOPE_CHECK_CATEGORIES]);
  const [days, setDays] = useState(7);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const keys = useActionKeys('create-scope');
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedRepo) return;
    setBusy(true);
    setError(null);
    const sig = JSON.stringify([name.trim(), selectedRepo.id, recipe.trim(), categories, days, notes.trim()]);
    try {
      // Built once per action: a retry resends the same expiry under the same key.
      const body = keys.payloadFor(sig, () => {
        const defaults = scopeBody(selectedRepo.id, new Date());
        return {
          ...defaults,
          name: name.trim(),
          targets: [{ ...defaults.targets[0]!, build_recipe_ref: recipe.trim() }],
          allowed_check_categories: categories,
          expires_at: new Date(Date.now() + days * 86_400_000).toISOString(),
          notes: notes.trim() || null,
        };
      });
      await api().createScope(project.id, body, { idempotencyKey: keys.keyFor(sig) });
      keys.done();
      setName('');
      onCreated();
    } catch (err) { setError(err); } finally { setBusy(false); }
  };
  return (
    <Panel title="Request a scope">
      <p className="mb-3 text-sm text-muted" data-testid="request-scope-note">{REQUEST_SCOPE_NOTE}</p>
      {!selectedRepo ? <Empty>Connect a repository first.</Empty> : (
        <form onSubmit={submit} className="flex flex-col gap-3">
          <Field label="Name"><input className={inputClass} value={name} onChange={e => setName(e.target.value)} required name="scope_name" /></Field>
          <p className="text-sm text-muted" data-testid="scope-selected-repo">Repository (sandbox build target): <span className="font-mono text-ink">{selectedRepo.full_name}</span></p>
          <Field label="Build recipe path" hint="Relative to the repository root."><input className={`${inputClass} font-mono`} value={recipe} onChange={e => setRecipe(e.target.value)} required name="recipe" /></Field>
          <fieldset className="text-sm">
            <legend className="mb-1 text-muted">Allowed check categories</legend>
            {SCOPE_CHECK_CATEGORIES.map(c => (
              <label key={c} className="flex items-center gap-2 py-0.5">
                <input type="checkbox" checked={categories.includes(c)} onChange={e => setCategories(cs => e.target.checked ? [...cs, c] : cs.filter(x => x !== c))} />
                <Mono>{c}</Mono>
              </label>
            ))}
          </fieldset>
          <Field label="Expires after (days, max 90)"><input type="number" min={1} max={90} className={inputClass} value={days} onChange={e => setDays(Number(e.target.value))} name="days" /></Field>
          <Field label="Notes"><input className={inputClass} value={notes} onChange={e => setNotes(e.target.value)} name="notes" /></Field>
          <Button type="submit" variant="primary" disabled={busy || !name.trim() || categories.length === 0}>Request scope</Button>
          {error !== null && <ErrorState error={error} context="Scope not requested" />}
        </form>
      )}
    </Panel>
  );
}
