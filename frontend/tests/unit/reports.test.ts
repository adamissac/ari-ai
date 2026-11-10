import type { StreamEvent } from '@hackatl/frontend-transport';
import { describe, expect, it } from 'vitest';
import { reportLinks } from '@/lib/reports';

const event = (data: Record<string, unknown>) => ({ data }) as StreamEvent;

describe('reportLinks', () => {
  it('links the reports a run stored', () => {
    const links = reportLinks([event({}), event({ sarif_artifact_id: 'art_01M6FV69QHC2DSDJ49FH8X2HXW', roe_artifact_id: 'art_01M6FV69QMBSY3HJAJ0N4D5SJB' })]);
    expect(links.map(l => l.href)).toEqual(['/api/v1/artifacts/art_01M6FV69QHC2DSDJ49FH8X2HXW', '/api/v1/artifacts/art_01M6FV69QMBSY3HJAJ0N4D5SJB']);
  });
  it('shows nothing when no report was stored or the id is not an artifact id', () => {
    expect(reportLinks([event({})])).toEqual([]);
    expect(reportLinks([event({ sarif_artifact_id: '../auth/logout' }), event({ roe_artifact_id: 7 })])).toEqual([]);
  });
});
