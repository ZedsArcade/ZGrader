"use client";

import { useRef, useState, type ChangeEvent } from "react";
import { Card, ProgressBar } from "@heroui/react";
import Button from "@/components/Button";
import { toastError } from "@/lib/toast";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

function ScanSlot({
  side,
  label,
  hint,
  token,
  code,
  onUploaded,
}: {
  side: api.ScanSide;
  label: string;
  hint?: string;
  token: string;
  code: string;
  onUploaded: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  async function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      const updated = await api.uploadScan(token, code, side, file);
      onUploaded(updated);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.upload.uploadFailed);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border p-4">
      <p className="text-sm font-semibold text-foreground">{label}</p>
      {hint && <p className="text-sm text-muted">{hint}</p>}
      {uploading ? (
        <ProgressBar aria-label={t.upload.uploading} isIndeterminate className="w-full">
          <ProgressBar.Track>
            <ProgressBar.Fill />
          </ProgressBar.Track>
        </ProgressBar>
      ) : (
        <>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            capture
            onChange={handleChange}
            className="hidden"
          />
          <Button variant="outline" size="sm" onPress={() => inputRef.current?.click()}>
            {t.upload.chooseFile}
          </Button>
        </>
      )}
    </div>
  );
}

export default function UploadStep({
  code,
  token,
  scanSides,
  onUploaded,
}: {
  code: string;
  token: string;
  scanSides: api.ScanSide[];
  onUploaded: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const hasFront = scanSides.includes("front");
  const hasBack = scanSides.includes("back");

  if (hasFront && hasBack) return null;

  return (
    <Card>
      <Card.Header>
        <Card.Title>{hasFront ? t.upload.frontUploadedTitle : t.upload.title}</Card.Title>
        <Card.Description>{hasFront ? t.upload.frontUploadedNote : t.upload.subtitle}</Card.Description>
      </Card.Header>
      <Card.Content className={hasFront ? undefined : "grid gap-4 sm:grid-cols-2"}>
        {!hasFront && (
          <ScanSlot side="front" label={t.upload.frontLabel} token={token} code={code} onUploaded={onUploaded} />
        )}
        {!hasBack && (
          <ScanSlot
            side="back"
            label={t.upload.backLabel}
            hint={hasFront ? undefined : t.upload.backHint}
            token={token}
            code={code}
            onUploaded={onUploaded}
          />
        )}
      </Card.Content>
    </Card>
  );
}
