import { Alert } from "@heroui/react";
import Button from "@/components/Button";

export default function ErrorState({
  message,
  onRetry,
  retryLabel = "Retry",
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <Alert status="danger">
      <Alert.Indicator>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3" />
          <path d="M8 5v3.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          <circle cx="8" cy="11" r="0.8" fill="currentColor" />
        </svg>
      </Alert.Indicator>
      <Alert.Content>
        <Alert.Description>{message}</Alert.Description>
      </Alert.Content>
      {onRetry && (
        <Button variant="outline" size="sm" onPress={onRetry}>
          {retryLabel}
        </Button>
      )}
    </Alert>
  );
}
