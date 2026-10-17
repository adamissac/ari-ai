import { BundleError, loadBundle } from '@/lib/lab-bundle';

export const dynamic = 'force-dynamic';

export async function GET(_request: Request, ctx: { params: Promise<{ protocol: string }> }) {
  const { protocol } = await ctx.params;
  try {
    return Response.json(await loadBundle(protocol), { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    if (error instanceof BundleError) return Response.json({ error: error.message }, { status: error.status });
    throw error;
  }
}
