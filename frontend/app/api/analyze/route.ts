import { backendOrigin } from '@/lib/backend-proxy';
import { LiveError, liveAnalysis, type GitHubCommit } from '@/lib/live-analysis';

/** Live analyses take one model call of up to a few minutes. */
export const maxDuration = 300;
export const dynamic = 'force-dynamic';

const FULL_NAME = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const SHA = /^[0-9a-f]{40}$/;

const fail = (status: number, code: string, message: string) => Response.json({ error: { code, message } }, { status });

/**
 * POST { repo: "owner/name", sha } → live analysis of that commit. Only for a signed-in user who
 * can reach the repository through their GitHub App installation, as checked by the control plane
 * with their session cookie, so the server's model key cannot be spent on arbitrary repositories.
 */
export async function POST(request: Request): Promise<Response> {
  let body: { repo?: unknown; sha?: unknown };
  try { body = await request.json(); } catch { return fail(400, 'BAD_REQUEST', 'Expected a JSON body.'); }
  const repo = typeof body.repo === 'string' ? body.repo : '';
  const sha = typeof body.sha === 'string' ? body.sha.toLowerCase() : '';
  if (!FULL_NAME.test(repo) || !SHA.test(sha)) return fail(400, 'BAD_REQUEST', 'Expected repo "owner/name" and a 40-character commit SHA.');

  const commit = await loadCommit(request, repo, sha);
  if (commit instanceof Response) return commit;

  try {
    return Response.json(await liveAnalysis(repo, sha, commit));
  } catch (error) {
    if (error instanceof LiveError) return fail(error.status, error.code, error.message);
    console.error('live analysis failed', error);
    return fail(500, 'INTERNAL', 'The live analysis failed unexpectedly.');
  }
}

async function loadCommit(
  request: Request,
  repo: string,
  sha: string,
): Promise<GitHubCommit | Response> {
  const cookie = request.headers.get('cookie');
  if (!cookie) return fail(401, 'UNAUTHENTICATED', 'Sign in first.');
  let res: Response;
  try {
    const params = new URLSearchParams({ repo, sha });
    res = await fetch(`${backendOrigin()}/api/v1/github/commit?${params}`, {
      headers: { cookie, accept: 'application/json' },
      cache: 'no-store',
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    return fail(502, 'SUBSYSTEM_UNAVAILABLE', 'Could not reach the control plane to read this commit.');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null) as {
      error?: { code?: unknown; message?: unknown };
    } | null;
    return fail(
      res.status,
      typeof body?.error?.code === 'string' ? body.error.code : 'SUBSYSTEM_UNAVAILABLE',
      typeof body?.error?.message === 'string'
        ? body.error.message
        : 'The control plane could not read this commit.',
    );
  }
  try {
    return await res.json() as GitHubCommit;
  } catch {
    return fail(502, 'SUBSYSTEM_UNAVAILABLE', 'The control plane returned an unreadable commit.');
  }
}
