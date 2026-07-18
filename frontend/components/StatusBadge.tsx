import type { SubmissionStatus } from "@/lib/api";

const STATUS_STYLES: Record<SubmissionStatus, string> = {
  created: "badge-neutral",
  awaiting_scans: "badge-neutral",
  processing: "badge-info",
  draft_ready: "badge-warning",
  approved: "badge-info",
  published: "badge-success",
  error: "badge-danger",
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
  return <span className={`badge ${STATUS_STYLES[status]}`}>{STATUS_LABELS[status]}</span>;
}
