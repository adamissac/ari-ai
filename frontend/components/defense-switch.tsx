'use client';

import type { Project } from '@hackatl/frontend-transport';
import { useState } from 'react';
import { ErrorState } from '@/components/ui';
import { api } from '@/lib/api';

export function DefenseSwitch({
  project,
  onChange,
  tone = 'light',
}: {
  project: Project;
  onChange?: (next: Project) => void;
  tone?: 'dark' | 'light';
}) {
  const dark = tone === 'dark';
  const projectEnabled = project.settings.monitoring_policy.enabled;
  const [toggleState, setToggleState] = useState({
    projectId: project.id,
    projectEnabled,
    enabled: projectEnabled,
  });
  if (toggleState.projectId !== project.id || toggleState.projectEnabled !== projectEnabled) {
    setToggleState({ projectId: project.id, projectEnabled, enabled: projectEnabled });
  }
  const on = toggleState.enabled;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const buttonTone = dark
    ? 'border-white/15 bg-white/5 text-white hover:bg-white/10'
    : 'border-line bg-panel-2 text-ink hover:bg-panel';
  const statusTone = dark ? 'text-white/75' : 'text-muted';
  const offDotTone = dark ? 'bg-white/30' : 'bg-line';
  const hintTone = dark ? 'text-white/55' : 'text-muted';

  const toggle = async () => {
    const previous = on;
    const enabled = !previous;
    setToggleState(current => ({ ...current, enabled }));
    setBusy(true);
    setError(null);
    try {
      const next = await api().updateProject(project.id, {
        name: project.name,
        settings: {
          ...project.settings,
          monitoring_policy: { ...project.settings.monitoring_policy, enabled },
        },
      });
      setToggleState(current => ({ ...current, enabled: next.settings.monitoring_policy.enabled }));
      onChange?.(next);
    } catch (err) {
      setToggleState(current => ({ ...current, enabled: previous }));
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex w-fit flex-col gap-1.5">
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label="24/7 defense"
        data-testid="defense-switch"
        disabled={busy}
        onClick={() => void toggle()}
        className={`inline-flex items-center gap-3 rounded-full border px-3.5 py-2 text-sm transition disabled:cursor-wait disabled:opacity-70 ${buttonTone}`}
      >
        <span>24/7 defense</span>
        <span className={`inline-flex items-center gap-1.5 text-xs ${statusTone}`}>
          <span aria-hidden="true" className={`h-2 w-2 rounded-full ${on ? 'bg-emerald-400' : offDotTone}`} />
          {on ? 'On' : 'Off'}
        </span>
      </button>
      <p className={`text-xs ${hintTone}`}>
        {on ? 'Watching every push and re-checking what changed.' : 'Paused. Pushes are recorded but not re-checked.'}
      </p>
      {error !== null && <ErrorState error={error} context="Could not change 24/7 defense (only project owners can)" />}
    </div>
  );
}
