import { ApiClient, ApiError, readJson } from './client.js';
import { decode, ProtocolError } from './contracts.js';
import type { StreamEvent, ErrorResponse } from './contracts.js';

interface Frame { id: string; event: string; data: string; retry?: number }
export type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'completed' | 'aborted' | 'failed';
export interface StreamOptions {
  after?: number;
  signal?: AbortSignal;
  maxReconnects?: number;
  retryMs?: number;
  maxRetryMs?: number;
  maxFrameBytes?: number;
  onConnection?: (state: ConnectionState) => void;
}
const terminal = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXHAUSTED']);

// SSE framing follows the browser event stream rules, including CRLF across
// chunks, BOM, comments and multiline data. A partial EOF record is not an event.
export async function* frames(body: ReadableStream<Uint8Array>, maxBytes = 1024 * 1024): AsyncGenerator<Frame> {
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  const encoder = new TextEncoder();
  let line = '';
  let skipLF = false;
  let first = true;
  let id = '';
  let event = '';
  let data: string[] = [];
  let bytes = 0;
  let retry: number | undefined;
  const accept = (): Frame | undefined => {
    bytes += encoder.encode(line).byteLength + 1;
    if (bytes > maxBytes) throw new ProtocolError('SSE frame exceeds size limit');
    if (line === '') {
      const frame = data.length ? { id, event, data: data.join('\n'), ...(retry === undefined ? {} : { retry }) } : undefined;
      // retry-only records still control reconnection but do not emit model data.
      const control = !frame && retry !== undefined ? { id: '', event: '', data: '', retry } : undefined;
      id = ''; event = ''; data = []; bytes = 0; retry = undefined;
      return frame ?? control;
    }
    if (line.startsWith(':')) return;
    const colon = line.indexOf(':');
    const field = colon < 0 ? line : line.slice(0, colon);
    let value = colon < 0 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'data') data.push(value);
    else if (field === 'event') event = value;
    else if (field === 'id' && !value.includes('\0')) id = value;
    else if (field === 'retry' && /^\d+$/.test(value) && Number.isSafeInteger(Number(value))) retry = Number(value);
  };
  try {
    for (;;) {
      const chunk = await reader.read();
      let text: string;
      try { text = chunk.done ? decoder.decode() : decoder.decode(chunk.value, { stream: true }); }
      catch { throw new ProtocolError('Invalid SSE UTF-8'); }
      for (const char of text) {
        if (first) { first = false; if (char === '\uFEFF') continue; }
        if (skipLF) { skipLF = false; if (char === '\n') continue; }
        if (char === '\r' || char === '\n') {
          const frame = accept(); line = ''; skipLF = char === '\r';
          if (frame) yield frame;
        } else {
          line += char;
          if (line.length + bytes > maxBytes) throw new ProtocolError('SSE frame exceeds size limit');
        }
      }
      if (chunk.done) break;
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = (): void => { clearTimeout(timer); signal?.removeEventListener('abort', abort); reject(signal?.reason ?? new DOMException('Aborted', 'AbortError')); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, ms);
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
  });
}

/** Yield only validated persisted events. Retain the last yielded seq to resume
 * across remounts; side effects in UI consumers must be idempotent by seq.
 * EOF is never treated as successful completion without a terminal event/state.
 */
export async function* watchAssessment(api: ApiClient, assessmentId: string, options: StreamOptions = {}): AsyncGenerator<StreamEvent> {
  if (!/^asm_[A-Za-z0-9_-]{8,64}$/.test(assessmentId)) throw new ProtocolError('Invalid assessment identifier');
  let cursor = options.after ?? 0;
  const maximum = options.maxReconnects ?? 5;
  const maxRetry = options.maxRetryMs ?? 10000;
  let retry = options.retryMs ?? 1000;
  const frameLimit = options.maxFrameBytes ?? 1024 * 1024;
  if (![cursor, maximum, maxRetry, retry, frameLimit].every(v => Number.isSafeInteger(v) && v >= 0) || frameLimit < 1) {
    throw new ProtocolError('Invalid stream limits');
  }
  let reconnects = 0;
  let completed = false;
  let failed = false;
  try {
    for (;;) {
      options.signal?.throwIfAborted();
      options.onConnection?.(reconnects === 0 ? 'connecting' : 'reconnecting');
      let failure: unknown;
      try {
        const response = await api.fetch(`${api.baseUrl}/assessments/${assessmentId}/events?after=${cursor}`, {
          credentials: 'include',
          headers: { Accept: 'text/event-stream', ...(cursor ? { 'Last-Event-ID': String(cursor) } : {}) },
          ...(options.signal ? { signal: options.signal } : {}),
        });
        if (!response.ok) {
          if (response.status === 401) api.clearSession();
          throw new ApiError(response.status, decode<ErrorResponse>('ErrorResponse', await readJson(response)).error);
        }
        if (!response.headers.get('content-type')?.toLowerCase().startsWith('text/event-stream') || !response.body) {
          await response.body?.cancel();
          throw new ProtocolError('Expected an SSE response');
        }
        options.onConnection?.('connected');
        for await (const frame of frames(response.body, frameLimit)) {
          options.signal?.throwIfAborted();
          if (frame.retry !== undefined) retry = Math.min(frame.retry, maxRetry);
          if (!frame.data) continue;
          let raw: unknown;
          try { raw = JSON.parse(frame.data) as unknown; }
          catch { throw new ProtocolError('Invalid SSE JSON'); }
          const event = decode<StreamEvent>('StreamEvent', raw);
          if (!Number.isSafeInteger(event.seq) || frame.id !== String(event.seq) || frame.event !== event.type || event.assessment_id !== assessmentId) {
            throw new ProtocolError('SSE envelope does not match its persisted event');
          }
          if (event.seq <= cursor) continue;
          cursor = event.seq;
          yield event;
          if (event.type === 'assessment.completed' || event.type === 'assessment.failed' || (event.state && terminal.has(event.state))) {
            completed = true;
            options.onConnection?.('completed');
            return;
          }
        }
        // Resuming an already terminal assessment may return an empty stream.
        const detail = await api.assessment(assessmentId, options.signal ? { signal: options.signal } : {});
        if (terminal.has(detail.assessment.state)) {
          completed = true;
          options.onConnection?.('completed');
          return;
        }
        failure = new Error('Assessment stream closed before a terminal state');
      } catch (error) {
        if (options.signal?.aborted) throw error;
        if (error instanceof ProtocolError || (error instanceof ApiError && error.status !== 429 && error.status < 500)) throw error;
        failure = error;
      }
      if (reconnects >= maximum) throw failure;
      reconnects++;
      options.onConnection?.('reconnecting');
      await delay(Math.min(retry * 2 ** Math.min(reconnects - 1, 10), maxRetry), options.signal);
    }
  } catch (error) {
    failed = true;
    options.onConnection?.(options.signal?.aborted ? 'aborted' : 'failed');
    throw error;
  } finally {
    // Consumer cancellation also closes the reader through generator finalization.
    if (!completed && !failed && !options.signal?.aborted) options.onConnection?.('aborted');
  }
}
