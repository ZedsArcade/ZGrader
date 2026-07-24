"use client";

import { useRef, useState, type ChangeEvent } from "react";
import { Card, ProgressBar } from "@heroui/react";
import Button from "@/components/Button";
import CropAdjustStep from "@/components/CropAdjustStep";
import { toastError } from "@/lib/toast";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

function ScanSlot({
  side,
  label,
  hint,
  token,
  code,
  uploaded,
  onUploaded,
}: {
  side: api.ScanSide;
  label: string;
  hint?: string;
  token: string;
  code: string;
  uploaded: boolean;
  onUploaded: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  // A side already in scan_sides (e.g. after a page refresh mid-crop-
  // confirm) skips straight to the crop-adjust UI instead of re-showing the
  // file picker.
  const [awaitingCrop, setAwaitingCrop] = useState(uploaded);

  async function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadScan(token, code, side, file);
      setAwaitingCrop(true);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.upload.uploadFailed);
    } finally {
      setUploading(false);
    }
  }

  if (awaitingCrop) {
    return (
      <CropAdjustStep
        token={token}
        code={code}
        side={side}
        onConfirmed={(updated) => {
          setAwaitingCrop(false);
          onUploaded(updated);
        }}
      />
    );
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
  confirmedSides,
  onUploaded,
}: {
  code: string;
  token: string;
  scanSides: api.ScanSide[];
  confirmedSides: api.ScanSide[];
  onUploaded: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const frontDone = confirmedSides.includes("front");
  const backDone = confirmedSides.includes("back");

  if (frontDone && backDone) return null;

  return (
    <Card>
      <Card.Header>
        <Card.Title>{frontDone ? t.upload.frontUploadedTitle : t.upload.title}</Card.Title>
        <Card.Description>{frontDone ? t.upload.frontUploadedNote : t.upload.subtitle}</Card.Description>
      </Card.Header>
      <Card.Content className={frontDone ? undefined : "grid gap-4 sm:grid-cols-2"}>
        {!frontDone && (
          <ScanSlot
            side="front"
            label={t.upload.frontLabel}
            token={token}
            code={code}
            uploaded={scanSides.includes("front")}
            onUploaded={onUploaded}
          />
        )}
        {!backDone && (
          <ScanSlot
            side="back"
            label={t.upload.backLabel}
            hint={frontDone ? undefined : t.upload.backHint}
            token={token}
            code={code}
            uploaded={scanSides.includes("back")}
            onUploaded={onUploaded}
          />
        )}
      </Card.Content>
    </Card>
  );
}
