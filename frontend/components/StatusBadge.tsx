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

export default function StatusBadge({ status, locale = "en" }: { status: SubmissionStatus; locale?: Locale }) {
  const t = getDictionary(locale);
  return (
    <Chip color={STATUS_COLOR[status]} variant="soft" size="sm">
      {t.status[status]}
    </Chip>
  );
}
