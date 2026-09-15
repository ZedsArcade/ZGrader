import { Card, ProgressBar } from "@heroui/react";
import { getDictionary, type Locale } from "@/lib/i18n/context";
import type { SubmissionStatus } from "@/lib/api";

export default function ProcessingState({
  status,
  locale = "en",
  stillWorking = false,
}: {
  status: SubmissionStatus;
  locale?: Locale;
  /** Polling gave up: say we'll email rather than spin forever. */
  stillWorking?: boolean;
}) {
  const t = getDictionary(locale);
  const title = status === "processing" ? t.submissionDetail.processingTitle : t.submissionDetail.awaitingScansTitle;

  return (
    <Card>
      <Card.Content className="flex flex-col items-center gap-4 py-8 text-center">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="text-sm text-muted">
          {stillWorking ? t.checkFlow.stillWorking : t.submissionDetail.processingDescription}
        </p>
        {!stillWorking && (
          <ProgressBar aria-label={title} isIndeterminate className="w-full max-w-xs">
            <ProgressBar.Track>
              <ProgressBar.Fill />
            </ProgressBar.Track>
          </ProgressBar>
        )}
      </Card.Content>
    </Card>
  );
}
