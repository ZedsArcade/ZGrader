"use client";

import { useEffect, useRef, useState } from "react";

const FAST_MS = 3_000;
const SLOW_MS = 10_000;
const FAST_FOR_MS = 60_000;
const GIVE_UP_MS = 600_000;

/**
 * Re-reads a submission while `active` is true, so a page that lands
 * mid-analysis finishes on its own instead of waiting for a reload.
 *
 * Every 3s for the first minute, then every 10s; paused while the tab is
 * hidden and resumed the moment it is shown; abandoned after 10 minutes,
 * when the caller shows "we'll email you". Worst case is about a third of
 * the submission_read allowance (300 per 5 minutes per address).
 *
 * Returns whether it gave up.
 */
export function useSubmissionPoll(active: boolean, poll: () => Promise<void>): boolean {
  const [timedOut, setTimedOut] = useState(false);
  const pollRef = useRef(poll);

  useEffect(() => {
    pollRef.current = poll;
  });

  useEffect(() => {
    if (!active) return;
    const started = Date.now();
    let timer: number | undefined;
    let cancelled = false;

    const schedule = () => {
      const elapsed = Date.now() - started;
      if (elapsed >= GIVE_UP_MS) {
        setTimedOut(true);
        return;
      }
      timer = window.setTimeout(tick, elapsed < FAST_FOR_MS ? FAST_MS : SLOW_MS);
    };
    const tick = async () => {
      if (cancelled || document.hidden) return; // resumed by visibilitychange
      try {
        await pollRef.current();
      } catch {
        // A failed read is retried on the next tick; nothing to show.
      }
      if (!cancelled) schedule();
    };
    const onVisibility = () => {
      if (!document.hidden && !cancelled) {
        window.clearTimeout(timer);
        void tick();
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    schedule();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [active]);

  return timedOut;
}
