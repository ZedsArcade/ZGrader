import Link from "next/link";
import { EmptyState as HeroEmptyState, buttonVariants, cn } from "@heroui/react";

export default function EmptyState({
  title,
  description,
  actionLabel,
  actionHref,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  actionHref?: string;
}) {
  return (
    <HeroEmptyState.Root className="flex flex-col items-center gap-3 py-10 text-center">
      <svg
        width="40"
        height="40"
        viewBox="0 0 40 40"
        fill="none"
        aria-hidden="true"
        className="text-muted"
      >
        <rect x="7" y="10" width="26" height="20" rx="3" stroke="currentColor" strokeWidth="1.5" />
        <path d="M7 16h26" stroke="currentColor" strokeWidth="1.5" />
        <path d="M14 23h4M14 27h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <div>
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-1 text-sm text-muted">{description}</p>
      </div>
      {actionLabel && actionHref && (
        <Link href={actionHref} className={cn(buttonVariants({ variant: "primary", size: "sm" }), "btn-press btn-neon-hover")}>
          {actionLabel}
        </Link>
      )}
    </HeroEmptyState.Root>
  );
}
