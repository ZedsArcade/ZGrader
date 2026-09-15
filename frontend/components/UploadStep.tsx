"use client";

import { useRef, useState, type ChangeEvent } from "react";
import { Card, ProgressBar } from "@heroui/react";
import Button from "@/components/Button";
import CropAdjustStep from "@/components/CropAdjustStep";
import { toastError } from "@/lib/toast";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

/**
 * The back photo, offered once the front has a result. The front goes through
 * CheckFlow; this completes a check, and adding it never charges again.
 */
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
  const cameraRef = useRef<HTMLInputElement>(null);
  const libraryRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  // A back already uploaded (a refresh mid-crop) goes straight to the crop.
  const [awaitingCrop, setAwaitingCrop] = useState(scanSides.includes("back"));

  async function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadScan(token, code, "back", file);
      setAwaitingCrop(true);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.upload.uploadFailed);
    } finally {
      setUploading(false);
    }
  }

  return (
    <Card>
      <Card.Header>
        <Card.Title>{t.checkFlow.backTitle}</Card.Title>
        <Card.Description>{t.checkFlow.backBody}</Card.Description>
      </Card.Header>
      <Card.Content>
        {awaitingCrop ? (
          <CropAdjustStep
            token={token}
            code={code}
            side="back"
            onConfirmed={(updated) => {
              setAwaitingCrop(false);
              onUploaded(updated);
            }}
          />
        ) : uploading ? (
          <ProgressBar aria-label={t.upload.uploading} isIndeterminate className="w-full">
            <ProgressBar.Track>
              <ProgressBar.Fill />
            </ProgressBar.Track>
          </ProgressBar>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={handleChange} className="hidden" />
            <input ref={libraryRef} type="file" accept="image/*" onChange={handleChange} className="hidden" />
            <Button variant="outline" onPress={() => cameraRef.current?.click()}>
              {t.checkFlow.takePhoto}
            </Button>
            <Button variant="outline" onPress={() => libraryRef.current?.click()}>
              {t.checkFlow.choosePhoto}
            </Button>
          </div>
        )}
      </Card.Content>
    </Card>
  );
}
