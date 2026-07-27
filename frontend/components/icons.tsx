/**
 * Inline SVG icons, shared by the footer and the contact page.
 *
 * Hand-rolled rather than an icon package: the app already draws its icons
 * this way (EmptyState, ErrorState, nav-drawer) and a handful of glyphs isn't
 * worth a dependency. Every icon takes its size from `className` and paints in
 * `currentColor`, so the caller controls both.
 */

const BASE = {
  viewBox: "0 0 24 24",
  "aria-hidden": true,
  focusable: "false",
} as const;

export interface IconProps {
  className?: string;
}

const DEFAULT_SIZE = "h-5 w-5";

// -- Social ---------------------------------------------------------------

export function InstagramIcon({ className = DEFAULT_SIZE }: IconProps) {
  return (
    <svg {...BASE} fill="currentColor" className={className}>
      <path d="M12 2c2.72 0 3.06.01 4.12.06 1.07.05 1.8.22 2.43.46.66.26 1.22.6 1.77 1.16.56.55.9 1.11 1.16 1.77.24.63.41 1.36.46 2.43.05 1.06.06 1.4.06 4.12s-.01 3.06-.06 4.12c-.05 1.07-.22 1.8-.46 2.43a4.9 4.9 0 0 1-1.16 1.77c-.55.56-1.11.9-1.77 1.16-.63.24-1.36.41-2.43.46-1.06.05-1.4.06-4.12.06s-3.06-.01-4.12-.06c-1.07-.05-1.8-.22-2.43-.46a4.9 4.9 0 0 1-1.77-1.16 4.9 4.9 0 0 1-1.16-1.77c-.24-.63-.41-1.36-.46-2.43C2.01 15.06 2 14.72 2 12s.01-3.06.06-4.12c.05-1.07.22-1.8.46-2.43.26-.66.6-1.22 1.16-1.77.55-.56 1.11-.9 1.77-1.16.63-.24 1.36-.41 2.43-.46C8.94 2.01 9.28 2 12 2Zm0 1.8c-2.67 0-2.99.01-4.04.06-.98.04-1.5.2-1.86.34-.47.18-.8.4-1.15.75-.35.35-.57.68-.75 1.15-.14.36-.3.88-.34 1.86-.05 1.05-.06 1.37-.06 4.04s.01 2.99.06 4.04c.04.98.2 1.5.34 1.86.18.47.4.8.75 1.15.35.35.68.57 1.15.75.36.14.88.3 1.86.34 1.05.05 1.37.06 4.04.06s2.99-.01 4.04-.06c.98-.04 1.5-.2 1.86-.34.47-.18.8-.4 1.15-.75.35-.35.57-.68.75-1.15.14-.36.3-.88.34-1.86.05-1.05.06-1.37.06-4.04s-.01-2.99-.06-4.04c-.04-.98-.2-1.5-.34-1.86a3.1 3.1 0 0 0-.75-1.15 3.1 3.1 0 0 0-1.15-.75c-.36-.14-.88-.3-1.86-.34-1.05-.05-1.37-.06-4.04-.06Zm0 3.07a5.13 5.13 0 1 1 0 10.26 5.13 5.13 0 0 1 0-10.26Zm0 8.46a3.33 3.33 0 1 0 0-6.66 3.33 3.33 0 0 0 0 6.66Zm6.54-8.66a1.2 1.2 0 1 1-2.4 0 1.2 1.2 0 0 1 2.4 0Z" />
    </svg>
  );
}

export function FacebookIcon({ className = DEFAULT_SIZE }: IconProps) {
  return (
    <svg {...BASE} fill="currentColor" className={className}>
      <path d="M24 12.07C24 5.4 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.05V9.41c0-3.02 1.79-4.69 4.53-4.69 1.31 0 2.69.24 2.69.24v2.96h-1.51c-1.49 0-1.96.93-1.96 1.89v2.26h3.33l-.53 3.49h-2.8V24C19.61 23.1 24 18.1 24 12.07Z" />
    </svg>
  );
}

export function XIcon({ className = DEFAULT_SIZE }: IconProps) {
  return (
    <svg {...BASE} fill="currentColor" className={className}>
      <path d="M17.53 3h3.06l-6.69 7.64L21.75 21h-6.16l-4.82-6.3L5.25 21H2.18l7.15-8.17L2.25 3h6.32l4.36 5.76L17.53 3Zm-1.07 16.15h1.7L7.62 4.76h-1.82l10.66 14.39Z" />
    </svg>
  );
}

export function WhatsAppIcon({ className = DEFAULT_SIZE }: IconProps) {
  return (
    <svg {...BASE} fill="currentColor" className={className}>
      <path d="M12.04 2c-5.5 0-9.96 4.46-9.96 9.96 0 1.76.46 3.48 1.34 5L2 22l5.16-1.35a9.92 9.92 0 0 0 4.88 1.25h.01c5.49 0 9.95-4.46 9.95-9.96A9.9 9.9 0 0 0 19.08 4.9 9.9 9.9 0 0 0 12.04 2Zm0 18.18h-.01a8.26 8.26 0 0 1-4.21-1.15l-.3-.18-3.13.82.84-3.06-.2-.31a8.24 8.24 0 0 1-1.26-4.39c0-4.56 3.71-8.27 8.28-8.27 2.21 0 4.29.86 5.85 2.43a8.22 8.22 0 0 1 2.42 5.85c0 4.57-3.71 8.26-8.28 8.26Zm4.54-6.19c-.25-.13-1.47-.72-1.7-.81-.23-.08-.4-.12-.56.13-.17.24-.64.8-.79.97-.14.16-.29.18-.54.06-.25-.13-1.05-.39-2-1.23-.74-.66-1.24-1.47-1.38-1.72-.15-.25-.02-.38.11-.5.11-.11.25-.29.37-.44.13-.14.17-.24.25-.41.09-.16.04-.31-.02-.43-.06-.13-.56-1.35-.77-1.84-.2-.49-.4-.42-.55-.43h-.47c-.16 0-.43.06-.65.31-.22.24-.85.83-.85 2.03 0 1.19.87 2.35.99 2.51.12.16 1.71 2.61 4.14 3.66.58.25 1.03.4 1.38.51.58.19 1.11.16 1.53.1.47-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.15-1.18-.06-.11-.23-.17-.48-.29Z" />
    </svg>
  );
}

// -- Contact --------------------------------------------------------------
// Stroked rather than filled, so they read as UI marks beside a label rather
// than competing with the filled brand logos above.

const STROKE = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

export function MailIcon({ className = DEFAULT_SIZE }: IconProps) {
  return (
    <svg {...BASE} {...STROKE} className={className}>
      <rect x="2.5" y="4.5" width="19" height="15" rx="2.5" />
      <path d="m3.5 6.5 8.5 6 8.5-6" />
    </svg>
  );
}

export function MapPinIcon({ className = DEFAULT_SIZE }: IconProps) {
  return (
    <svg {...BASE} {...STROKE} className={className}>
      <path d="M12 21.5s7-6.1 7-11.1a7 7 0 1 0-14 0c0 5 7 11.1 7 11.1Z" />
      <circle cx="12" cy="10" r="2.6" />
    </svg>
  );
}

export function StopwatchIcon({ className = DEFAULT_SIZE }: IconProps) {
  return (
    <svg {...BASE} {...STROKE} className={className}>
      <circle cx="12" cy="13.5" r="7.5" />
      <path d="M12 9.5v4l2.5 2M9.5 2.5h5M12 2.5V6M18.6 7.4l1.6-1.6" />
    </svg>
  );
}

/** Two figures side by side -- handover in person. */
export function PeopleIcon({ className = DEFAULT_SIZE }: IconProps) {
  return (
    <svg {...BASE} {...STROKE} className={className}>
      <circle cx="8.5" cy="8" r="3" />
      <circle cx="16.5" cy="9.5" r="2.4" />
      <path d="M2.5 19.5a6 6 0 0 1 12 0" />
      <path d="M15 14.6a5.2 5.2 0 0 1 6.5 4.9" />
    </svg>
  );
}
