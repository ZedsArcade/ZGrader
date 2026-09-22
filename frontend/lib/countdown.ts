/**
 * Formats the gap to `iso` as a coarse countdown: days and hours, or hours and
 * minutes inside a day. Shared by the header chip and the out-of-checks panel
 * so both say the same thing.
 *
 * Deliberately not second-by-second. The reset is up to a week away, so a
 * ticking seconds display would be noise that also forces a re-render every
 * second on every page.
 */
export function formatRemaining(
  iso: string,
  now: number,
  labels: { d: string; h: string; m: string }
): string | null {
  const ms = new Date(iso).getTime() - now;
  if (!Number.isFinite(ms) || ms <= 0) return null;

  const minutes = Math.floor(ms / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days >= 1) return `${days}${labels.d} ${hours % 24}${labels.h}`;
  if (hours >= 1) return `${hours}${labels.h} ${minutes % 60}${labels.m}`;
  return `${Math.max(1, minutes)}${labels.m}`;
}
