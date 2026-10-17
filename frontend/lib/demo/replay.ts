'use client';

import { useCallback, useEffect, useState } from 'react';

export const SPEEDS = [0.5, 1, 2, 4] as const;
export type Speed = (typeof SPEEDS)[number];

export interface Playback {
  position: number;
  playing: boolean;
  done: boolean;
  speed: Speed;
  setSpeed: (s: Speed) => void;
  toggle: () => void;
  seek: (p: number) => void;
  skip: () => void;
  restart: () => void;
}

/**
 * Playhead for the recorded run: advances one tool step at a time so the agents appear to
 * work in order, at the chosen speed, and can be paused or scrubbed. Reduced motion starts
 * at the end. `position === total` means finished.
 */
export function useReplay(total: number, stepMs = 650): Playback {
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState<Speed>(1);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPosition(total);
      setPlaying(false);
    }
  }, [total]);

  const running = playing && position < total;
  useEffect(() => {
    if (!running) return;
    const id = setTimeout(() => setPosition(p => p + 1), (position === 0 ? 900 : stepMs) / speed);
    return () => clearTimeout(id);
  }, [running, position, stepMs, speed]);

  const skip = useCallback(() => { setPosition(total); setPlaying(false); }, [total]);
  const restart = useCallback(() => { setPosition(0); setPlaying(true); }, []);
  const seek = useCallback((p: number) => { setPosition(Math.max(0, Math.min(total, p))); setPlaying(false); }, [total]);
  const toggle = useCallback(() => {
    if (position >= total) { setPosition(0); setPlaying(true); } else setPlaying(v => !v);
  }, [position, total]);
  return { position: Math.min(position, total), playing: running, done: position >= total, speed, setSpeed, toggle, seek, skip, restart };
}
