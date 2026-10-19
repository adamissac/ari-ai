import { backendOrigin } from '@/lib/backend-proxy';
import { LiveError, liveAnalysis } from '@/lib/live-analysis';

/** Live analyses take one model call of up to a few minutes. */
export const maxDuration = 300;
export const dynamic = 'force-dynamic';

const FULL_NAME = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const SHA = /^[0-9a-f]{40}$/;

const fail = (status: number, code: string, message: string) => Response.json({ error: { code, message } }, { status });

/**
 * POST { repo: "owner/name", sha } → live analysis of that commit. Only for a signed-in user who
 * can reach the repository through the GitHub App (checked against the control plane with their
 * own session cookie), so the server's model key cannot be spent on arbitrary repositories.
 */
export async function POST(request: Request): Promise<Response> {
  let body: { repo?: unknown; sha?: unknown };
  try { body = await request.json(); } catch { return fail(400, 'BAD_REQUEST', 'Expected a JSON body.'); }
  const repo = typeof body.repo === 'string' ? body.repo : '';
  const sha = typeof body.sha === 'string' ? body.sha.toLowerCase() : '';
  if (!FULL_NAME.test(repo) || !SHA.test(sha)) return fail(400, 'BAD_REQUEST', 'Expected repo "owner/name" and a 40-character commit SHA.');

  const access = await canReach(request, repo);
  if (access !== true) return access;

  try {
    return Response.json(await liveAnalysis(repo, sha));
  } catch (error) {
    if (error instanceof LiveError) return fail(error.status, error.code, error.message);
    console.error('live analysis failed', error);
    return fail(500, 'INTERNAL', 'The live analysis failed unexpectedly.');
  }
}

async function canReach(request: Request, repo: string): Promise<true | Response> {
  const cookie = request.headers.get('cookie');
  if (!cookie) return fail(401, 'UNAUTHENTICATED', 'Sign in first.');
  let res: Response;
  try {
    res = await fetch(`${backendOrigin()}/api/v1/github/repositories`, { headers: { cookie, accept: 'application/json' }, cache: 'no-store', signal: AbortSignal.timeout(15_000) });
  } catch {
    return fail(502, 'SUBSYSTEM_UNAVAILABLE', 'Could not reach the control plane to check repository access.');
  }
  if (res.status === 401) return fail(401, 'UNAUTHENTICATED', 'Sign in first.');
  if (!res.ok) return fail(502, 'SUBSYSTEM_UNAVAILABLE', 'Could not check repository access.');
  const list = (await res.json().catch(() => null)) as { items?: { full_name?: unknown }[] } | null;
  const ok = list?.items?.some(r => typeof r.full_name === 'string' && r.full_name.toLowerCase() === repo.toLowerCase());
  return ok ? true : fail(403, 'FORBIDDEN', 'This repository is not reachable through your GitHub App installation.');
}
