'use client';

import { useSyncExternalStore } from 'react';

function isDemoView(): boolean {
  return document.cookie.split(';').some(cookie => cookie.trim() === 'ari_demo_view=1');
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener('ari-demo-session-changed', onChange);
  return () => window.removeEventListener('ari-demo-session-changed', onChange);
}

export function useDemoView(): boolean {
  return useSyncExternalStore(subscribe, isDemoView, () => false);
}
