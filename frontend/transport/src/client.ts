import { decode, ProtocolError } from './contracts.js';
import type * as C from './contracts.js';

export type Fetch = typeof globalThis.fetch;
export interface Page<T> { items: T[]; next_cursor: string | null }
export interface RequestOptions { signal?: AbortSignal }
export class ApiError extends Error {
  override name = 'ApiError';
  constructor(readonly status: number, readonly error: C.ErrorBody) { super(error.message); }
}
export interface ClientOptions { baseUrl: string; fetch?: Fetch }
const segment = (id: string): string => {
  if (!/^[A-Za-z0-9_-]+$/.test(id)) throw new ProtocolError('Invalid resource identifier');
  return encodeURIComponent(id);
};

export class ApiClient {
  readonly baseUrl: string;
  readonly fetch: Fetch;
  private csrf: string | undefined;
  constructor(options: ClientOptions) {
    const url = new URL(options.baseUrl);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
      throw new ProtocolError('Expected an HTTP API URL without credentials, query or fragment');
    }
    this.baseUrl = url.href.replace(/\/$/, '');
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }
  clearSession(): void { this.csrf = undefined; }
  private async request(path: string, schema: Parameters<typeof decode>[0], options: RequestOptions = {}, body?: unknown, key?: string, envelope?: 'assessment'): Promise<unknown> {
    const headers = new Headers({ Accept: 'application/json' });
    if (body !== undefined) {
      if (!this.csrf && path !== '/auth/dev/login') throw new ProtocolError('Load the authenticated session before a mutation');
      headers.set('Content-Type', 'application/json');
      if (this.csrf) headers.set('X-CSRF-Token', this.csrf);
    }
    if (key !== undefined) {
      if (!key.trim()) throw new ProtocolError('An idempotency key is required');
      headers.set('Idempotency-Key', key);
    }
    const response = await this.fetch(this.baseUrl + path, {
      method: body === undefined ? 'GET' : 'POST', credentials: 'include', headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      ...(options.signal ? { signal: options.signal } : {}),
    });
    if (response.status === 401) this.clearSession();
    const value = await readJson(response);
    if (!response.ok) throw new ApiError(response.status, decode<C.ErrorResponse>('ErrorResponse', value).error);
    if (envelope) {
      if (!value || typeof value !== 'object' || !(envelope in value)) throw new ProtocolError('Invalid assessment acceptance envelope');
      return decode(schema, (value as Record<string, unknown>)[envelope]);
    }
    return decode(schema, value);
  }
  async session(options?: RequestOptions): Promise<C.MeResponse> {
    const me = await this.request('/me', 'MeResponse', options) as C.MeResponse;
    this.csrf = me.csrf_token;
    return me;
  }
  // Development-only backend endpoint, deliberately never called automatically.
  async devLogin(body: C.DevLoginRequest, options?: RequestOptions): Promise<C.MeResponse> {
    const me = await this.request('/auth/dev/login', 'MeResponse', options, body) as C.MeResponse;
    this.csrf = me.csrf_token;
    return me;
  }
  project(id: string, options?: RequestOptions): Promise<C.Project> {
    return this.request(`/projects/${segment(id)}`, 'Project', options) as Promise<C.Project>;
  }
  createProject(body: C.ProjectCreate, options?: RequestOptions): Promise<C.Project> {
    return this.request('/projects', 'Project', options, body) as Promise<C.Project>;
  }
  connectRepository(projectId: string, body: C.RepositoryConnect, options?: RequestOptions): Promise<C.Repository> {
    return this.request(`/projects/${segment(projectId)}/repositories`, 'Repository', options, body) as Promise<C.Repository>;
  }
  createSnapshot(repoId: string, body: C.SnapshotCreate, key: string, options?: RequestOptions): Promise<C.Snapshot> {
    return this.request(`/repositories/${segment(repoId)}/snapshots`, 'Snapshot', options, body, key) as Promise<C.Snapshot>;
  }
  snapshot(id: string, options?: RequestOptions): Promise<C.Snapshot> {
    return this.request(`/snapshots/${segment(id)}`, 'Snapshot', options) as Promise<C.Snapshot>;
  }
  createScope(projectId: string, body: C.ScopeCreate, options?: RequestOptions): Promise<C.AuthorizedScope> {
    return this.request(`/projects/${segment(projectId)}/scopes`, 'AuthorizedScope', options, body) as Promise<C.AuthorizedScope>;
  }
  approveScope(id: string, options?: RequestOptions): Promise<C.AuthorizedScope> {
    return this.request(`/scopes/${segment(id)}/approve`, 'AuthorizedScope', options, {}) as Promise<C.AuthorizedScope>;
  }
  startAssessment(projectId: string, body: C.AssessmentCreate, key: string, options?: RequestOptions): Promise<C.Assessment> {
    return this.request(`/projects/${segment(projectId)}/assessments`, 'Assessment', options, body, key, 'assessment') as Promise<C.Assessment>;
  }
  assessment(id: string, options?: RequestOptions): Promise<C.AssessmentDetail> {
    return this.request(`/assessments/${segment(id)}`, 'AssessmentDetail', options) as Promise<C.AssessmentDetail>;
  }
  decideApproval(id: string, body: C.ApprovalDecision, options?: RequestOptions): Promise<C.Approval> {
    return this.request(`/approvals/${segment(id)}/decision`, 'Approval', options, body) as Promise<C.Approval>;
  }
}

// Bounded reads prevent an error page or malicious stream from exhausting memory.
export async function readJson(response: Response, maxBytes = 8 * 1024 * 1024): Promise<unknown> {
  if (!response.headers.get('content-type')?.toLowerCase().includes('application/json')) {
    await response.body?.cancel();
    throw new ProtocolError('Expected a JSON response');
  }
  const reader = response.body?.getReader();
  if (!reader) throw new ProtocolError('Missing response body');
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let size = 0;
  let text = '';
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) throw new ProtocolError('JSON response exceeds size limit');
      text += decoder.decode(value, { stream: true });
    }
    text += decoder.decode();
    return JSON.parse(text) as unknown;
  } catch (error) {
    await reader.cancel().catch(() => undefined);
    if (error instanceof ProtocolError) throw error;
    throw new ProtocolError('Invalid JSON response');
  } finally { reader.releaseLock(); }
}
