import { Chip } from "@heroui/react";
import type { SubmissionStatus } from "@/lib/api";
import { getDictionary, type Locale } from "@/lib/i18n/context";

const STATUS_COLOR: Record<SubmissionStatus, "default" | "accent" | "warning" | "success" | "danger"> = {
  created: "default",
  awaiting_scans: "default",
  processing: "accent",
  draft_ready: "warning",
  approved: "accent",
  published: "success",
  error: "danger",
};

/**
 * The operator's words name pipeline states; a customer needs to know what is
 * happening to their card. Same colours, different vocabulary.
 */
export function customerStatusLabel(
  status: SubmissionStatus,
  flags: { mailIn: boolean; charged: boolean },
  locale: Locale
): string {
  const t = getDictionary(locale).customerStatus;
  switch (status) {
    case "created":
    case "awaiting_scans":
      // An uncharged photo draft is the customer's own unfinished work. A
      // mail-in -- or a submission charged under the old create-time rule --
      // is waiting on the post.
      return flags.mailIn || flags.charged ? t.awaitingCard : t.draft;
    case "processing":
      return t.analysing;
    case "draft_ready":
    case "approved":
      return t.inReview;
    case "published":
      return t.reportReady;
    case "error":
      return t.couldNotAnalyse;
  }
}

export default function StatusBadge({
  status,
  locale = "en",
  audience = "operator",
  mailIn = false,
  charged = false,
}: {
  status: SubmissionStatus;
  locale?: Locale;
  /** "operator" keeps the admin's pipeline vocabulary, and is the default so
   *  admin call sites need no change. */
  audience?: "customer" | "operator";
  mailIn?: boolean;
  charged?: boolean;
}) {
  const label =
    audience === "customer"
      ? customerStatusLabel(status, { mailIn, charged }, locale)
      : getDictionary(locale).status[status];
  return (
    <Chip color={STATUS_COLOR[status]} variant="soft" size="sm">
      {label}
    </Chip>
  );
}
