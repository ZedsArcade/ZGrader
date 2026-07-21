import { Card, ProgressBar } from "@heroui/react";
import { getDictionary, type Locale } from "@/lib/i18n/context";
import type { SubmissionStatus } from "@/lib/api";

export default function ProcessingState({
  status,
  locale = "en",
}: {
  status: SubmissionStatus;
  locale?: Locale;
}) {
  const t = getDictionary(locale);
  const title = status === "processing" ? t.submissionDetail.processingTitle : t.submissionDetail.awaitingScansTitle;

  return (
    <Card>
      <Card.Content className="flex flex-col items-center gap-4 py-8 text-center">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="text-sm text-muted">{t.submissionDetail.processingDescription}</p>
        <ProgressBar aria-label={title} isIndeterminate className="w-full max-w-xs">
          <ProgressBar.Track>
            <ProgressBar.Fill />
          </ProgressBar.Track>
        </ProgressBar>
      </Card.Content>
    </Card>
  );
}
