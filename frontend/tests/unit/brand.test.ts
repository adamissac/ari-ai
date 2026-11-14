import { describe, expect, it } from 'vitest';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST, BRAND_NAME, BRAND_TAGLINE } from '@/components/brand';

describe('brand copy', () => {
  it('does not say every fix is already proven or that the product ships it', () => {
    expect(`${BRAND_HEADLINE_REST} ${BRAND_TAGLINE}`.toLowerCase()).not.toMatch(/every fix proven|ship fast/);
    expect(BRAND_NAME).toBe('ARI');
    expect(BRAND_HEADLINE).toBe('FIND THE FLAW.');
    expect(BRAND_HEADLINE_REST).toBe('PROVE THE FIX.');
    expect(BRAND_TAGLINE).toMatch(/executed tests agree/);
  });
});
