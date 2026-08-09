/**
 * The left-to-right palette sweep when the visitor switches brands.
 *
 * Uses the browser's native View Transitions API directly rather than React's
 * <ViewTransition> component. Two reasons: the component needs
 * `experimental.viewTransition` turned on in next.config.ts, and it activates
 * on *navigation*, whereas the thing being animated here is a `data-brand`
 * attribute flip on <html>. Driving the API by hand keeps the animation
 * attached to the palette change that actually causes it.
 *
 * The whole effect is CSS (see the brand-sweep block in motion.css). This
 * module only decides *whether* to animate and which way the wave runs; the
 * `data-brand-sweep` attribute it sets is what the stylesheet keys off.
 *
 * Degrades in two directions, both to the same place -- an instant swap:
 *   - no startViewTransition (older Firefox, older Safari): skipped outright
 *   - prefers-reduced-motion: reduce: skipped outright
 * Neither is a broken state; the brand still changes, just without the wave.
 */

/** Which way the wave travels. Named for where it *finishes*. */
export type SweepDirection = "ltr" | "rtl";

const SWEEP_ATTRIBUTE = "data-brand-sweep";

type ViewTransitionDocument = Document & {
  startViewTransition?: (callback: () => void) => { finished: Promise<void> };
};

function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    // matchMedia is missing in some embedded webviews. Assuming "no preference"
    // would force motion on someone who asked for none, so assume the opposite.
    return true;
  }
}

/**
 * Runs `apply` inside a view transition that wipes the new palette across.
 *
 * `apply` must make its DOM change synchronously -- the API snapshots the page
 * before calling it and again immediately after, so anything deferred (a
 * router push, a setState) lands outside the transition and simply won't be
 * part of the animation. That is why the caller flips `data-brand` in here and
 * navigates separately.
 */
export function sweepBrandChange(direction: SweepDirection, apply: () => void): void {
  const doc = document as ViewTransitionDocument;

  if (typeof doc.startViewTransition !== "function" || prefersReducedMotion()) {
    apply();
    return;
  }

  const root = doc.documentElement;
  root.setAttribute(SWEEP_ATTRIBUTE, direction);

  const transition = doc.startViewTransition(apply);

  // Remove the attribute once the animation is done, so an unrelated view
  // transition later in the session doesn't inherit the wipe. `finished`
  // rejects if the transition is skipped or interrupted -- a rejection here is
  // not an error worth surfacing, it just means the sweep didn't run, so the
  // cleanup is attached to both outcomes.
  transition.finished
    .catch(() => undefined)
    .finally(() => root.removeAttribute(SWEEP_ATTRIBUTE));
}
