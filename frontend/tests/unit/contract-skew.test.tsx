import { cleanup, render, screen } from '@testing-library/react';
import { ProtocolError } from '@hackatl/frontend-transport';
import { afterEach, expect, it, vi } from 'vitest';
import { ErrorState } from '@/components/ui';
import { CONTRACT_SCHEMA_VERSION } from '../../../shared/generated/ts/contracts';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function pair(backend: string) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ frontend: { schemaVersion: CONTRACT_SCHEMA_VERSION }, backend: { schemaVersion: backend } }))));
}

it('tells the person to reload when the page predates the deployed contract', async () => {
  pair('9.9.9');
  render(<ErrorState error={new ProtocolError('Invalid Repository response')} />);
  expect((await screen.findByTestId('contract-skew')).textContent).toContain('Ari was updated since this page loaded');
  expect(screen.getByRole('button', { name: 'Reload the page' })).toBeTruthy();
});

it('does not blame a deploy when both sides run the same contract', async () => {
  pair(CONTRACT_SCHEMA_VERSION);
  render(<ErrorState error={new ProtocolError('Invalid Repository response')} />);
  expect((await screen.findByTestId('contract-skew')).textContent).toContain('real mismatch');
});

it('adds nothing to ordinary API errors', () => {
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  render(<ErrorState error={new Error('boom')} />);
  expect(screen.queryByTestId('contract-skew')).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
});
