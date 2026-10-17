import { describe, expect, it } from 'vitest';
import { BRAND_HEADLINE_REST, BRAND_TAGLINE } from '@/components/brand';

describe('brand copy', () => {
  it('does not say every fix is already proven or that the product ships it', () => {
    expect(`${BRAND_HEADLINE_REST} ${BRAND_TAGLINE}`.toLowerCase()).not.toMatch(/every fix proven|ship fast/);
    expect(BRAND_HEADLINE_REST).toMatch(/independent tests agree/);
    expect(BRAND_TAGLINE).toMatch(/executed tests agree/);
  });
});
