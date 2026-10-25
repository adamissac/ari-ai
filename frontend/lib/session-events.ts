import type { MeResponse } from '@hackatl/frontend-transport';

export const SESSION_CHANGED_EVENT = 'ari:session-changed';

export interface SessionChangedEventDetail {
  me: MeResponse | null;
}

export function notifySessionChanged(me: MeResponse | null): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent<SessionChangedEventDetail>(SESSION_CHANGED_EVENT, { detail: { me } }));
}
