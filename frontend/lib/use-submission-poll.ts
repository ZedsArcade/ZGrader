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
 * Returns whether it gave up. Resets when polling stops.
 */
export function useSubmissionPoll(active: boolean, poll: () => Promise<void>): boolean {
  const [timedOut, setTimedOut] = useState(false);
  const pollRef = useRef(poll);
  const inFlight = useRef(false);

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
      if (inFlight.current) return; // a poll is already outstanding
      inFlight.current = true;
      try {
        await pollRef.current();
      } catch {
        // A failed read is retried on the next tick; nothing to show.
      } finally {
        // Gated like schedule() below: a stale tick from a run this effect has
        // already torn down must not clear a newer run's in-flight flag --
        // the newer run's own cleanup already reset it once, for itself.
        if (!cancelled) inFlight.current = false;
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
      inFlight.current = false;
      setTimedOut(false);
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [active]);

  return timedOut;
}
