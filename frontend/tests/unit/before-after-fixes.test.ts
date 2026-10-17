import { describe, expect, it } from 'vitest';
import { beforeSide } from '@/lib/before-after';

describe('beforeSide for functional findings', () => {
  it('claims a failing test only for confirmed statuses', () => {
    for (const status of ['validated', 'diagnosed', 'patch_proposed', 'verified', 'patch_rejected', 'unresolved', 'hardened']) {
      expect(beforeSide({ kind: 'functional', status, validation: null }).headline).toBe('A test showed the wrong behaviour');
    }
  });
  it('a refuted finding did not reproduce', () => {
    expect(beforeSide({ kind: 'functional', status: 'refuted', validation: null }).headline).toBe('The problem did not reproduce');
  });
  it('inconclusive, closed, accepted_risk, needs_recheck and hypothesis record no reproduction', () => {
    for (const status of ['inconclusive', 'closed', 'accepted_risk', 'needs_recheck', 'hypothesis']) {
      const side = beforeSide({ kind: 'functional', status, validation: null });
      expect(side.headline).toBe('No reproduction recorded');
      expect(side.tone).toBe('neutral');
    }
  });
});
