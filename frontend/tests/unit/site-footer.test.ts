import { describe, expect, it } from 'vitest';
import { showsRecordsFooter } from '@/components/site-footer';

describe('records-only footer', () => {
  it('appears only where numbers come from saved records', () => {
    for (const p of ['/projects', '/projects/prj_1', '/projects/prj_1/assessments/asm_1', '/lab']) expect(showsRecordsFooter(p)).toBe(true);
    for (const p of ['/', '/pricing', '/pricing/team', '/projectsx', '/labs']) expect(showsRecordsFooter(p)).toBe(false);
  });
});
