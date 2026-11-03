import { describe, expect, it } from 'vitest';
import fixture from '@/lib/demo/console/fixtures.json';

const forbidden = [
  'e2e-alice',
  'payments-lite',
  'payments_lite',
  'acme',
  '99999999',
  'Selected payment change',
  'A different commit',
  'scripted',
  'fake',
];

function expectClean(value: unknown, path = 'fixture'): void {
  if (typeof value === 'string') {
    if (/^[0-9a-f]+$/i.test(value)) return;
    if (value.startsWith('retry:')) {
      const dataLines = value.split(/\r?\n/).filter(line => line.startsWith('data:'));
      for (const line of dataLines) {
        expectClean(JSON.parse(line.slice('data:'.length).trim()), `${path}.data`);
      }
      return;
    }
    for (const token of forbidden) {
      expect(value.toLowerCase(), `${path} contains ${token}`).not.toContain(token.toLowerCase());
    }
    expect(value, `${path} contains e2e`).not.toMatch(/\be2e\b/i);
  } else if (Array.isArray(value)) {
    value.forEach((child, index) => expectClean(child, `${path}[${index}]`));
  } else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) expectClean(child, `${path}.${key}`);
  }
}

describe('demo fixture hygiene', () => {
  it('does not contain harness names or placeholder data', () => {
    expectClean(fixture);
  });
});
