import { ApiClient, ApiError, ProtocolError } from '@hackatl/frontend-transport';

let client: ApiClient | undefined;

/** One browser client per tab: the CSRF token lives only in its memory. */
export function api(): ApiClient {
  if (typeof window === 'undefined') throw new Error('The API client is browser-only');
  client ??= new ApiClient({ baseUrl: `${window.location.origin}/api/v1` });
  return client;
}

/** Test seam: replace the singleton (unit tests inject a fetch double). */
export function setApiClient(next: ApiClient | undefined): void {
  client = next;
}

export interface DescribedError {
  kind: 'api' | 'protocol' | 'network' | 'aborted' | 'unknown';
  title: string;
  detail: string;
  code?: string;
  status?: number;
  requestId?: string | null;
}

/** Turn any thrown value into honest, user-facing text. Never echoes payloads. */
export function describeError(error: unknown): DescribedError {
  if (error instanceof ApiError) {
    return {
      kind: 'api',
      title: error.status === 401 ? 'Not signed in' : error.status === 403 ? 'Not permitted' : error.status === 404 ? 'Not found' : `Request failed (${error.status})`,
      detail: error.error.message,
      code: error.error.code,
      status: error.status,
      requestId: error.error.request_id,
    };
  }
  if (error instanceof ProtocolError) {
    return { kind: 'protocol', title: 'Backend response rejected', detail: `${error.message}. The response did not match the shared contract, so it was not rendered.` };
  }
  if (error instanceof Error && error.name === 'AbortError') {
    return { kind: 'aborted', title: 'Request cancelled', detail: 'The request was cancelled before it finished.' };
  }
  if (error instanceof TypeError) {
    return { kind: 'network', title: 'Backend unreachable', detail: 'The control-plane API did not respond. Nothing shown here is cached or simulated.' };
  }
  return { kind: 'unknown', title: 'Unexpected error', detail: error instanceof Error ? error.message : 'Unknown failure' };
}

/** A fresh idempotency key per user action; retries of the same action reuse it. */
export function idempotencyKey(action: string): string {
  return `${action}-${crypto.randomUUID()}`;
}
