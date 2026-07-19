import { Chip } from "@heroui/react";
import type { SubmissionStatus } from "@/lib/api";

const STATUS_COLOR: Record<SubmissionStatus, "default" | "accent" | "warning" | "success" | "danger"> = {
  created: "default",
  awaiting_scans: "default",
  processing: "accent",
  draft_ready: "warning",
  approved: "accent",
  published: "success",
  error: "danger",
};

const STATUS_LABELS: Record<SubmissionStatus, string> = {
  created: "Created",
  awaiting_scans: "Awaiting scans",
  processing: "Processing",
  draft_ready: "Draft ready",
  approved: "Approved",
  published: "Published",
  error: "Error",
};

export default function StatusBadge({ status }: { status: SubmissionStatus }) {
  return (
    <Chip color={STATUS_COLOR[status]} variant="soft" size="sm">
      {STATUS_LABELS[status]}
    </Chip>
  );
}
