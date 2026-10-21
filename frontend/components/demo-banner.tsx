/** Fixture mode is opt-in and must always be visible (MASTER_BUILD_SPEC §8, docs/14). */
export const DEMO_FIXTURES = process.env.NEXT_PUBLIC_DEMO_FIXTURES === '1';

export function DemoBanner() {
  if (!DEMO_FIXTURES) return null;
  return (
    <div role="status" className="border-b border-warn/50 bg-warn/15 px-4 py-3 text-center text-sm font-semibold text-warn shadow-sm">
      <div className="flex items-center justify-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-warn animate-pulse" />
        <span>DEMO DATA — fixture mode (NEXT_PUBLIC_DEMO_FIXTURES=1). Not a live backend.</span>
      </div>
    </div>
  );
}
