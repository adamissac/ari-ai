export const SESSION_CHANGED_EVENT = 'ari:session-changed';

export function notifySessionChanged(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
}
