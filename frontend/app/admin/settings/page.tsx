"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Checkbox, Input, Label, Skeleton, TextArea, TextField } from "@heroui/react";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/lib/auth-context";
import { useBranding } from "@/lib/branding-context";
import { toastError, toastSuccess } from "@/lib/toast";
import * as api from "@/lib/api";

function SettingsForm() {
  const { token } = useAuth();
  const { refresh: refreshBranding } = useBranding();
  const [settings, setSettings] = useState<api.Settings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) return;
    api
      .getSettings(token)
      .then(setSettings)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load settings"));
  }, [token]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token || !settings) return;
    setSaving(true);
    try {
      const updated = await api.updateSettings(token, settings);
      setSettings(updated);
      toastSuccess("Settings saved.");
      await refreshBranding();
    } catch (err) {
      toastError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  if (loadError && !settings) {
    return (
      <Card className="mx-auto max-w-2xl">
        <Card.Content>
          <p className="text-sm text-danger">{loadError}</p>
        </Card.Content>
      </Card>
    );
  }

  if (!settings) {
    return (
      <Card className="mx-auto max-w-2xl">
        <Card.Content>
          <div className="flex flex-col gap-4">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        </Card.Content>
      </Card>
    );
  }

  return (
    <Card className="mx-auto max-w-2xl">
      <Card.Header>
        <Card.Title>Business settings</Card.Title>
        <Card.Description>
          Branding shown on reports and the default auto-publish behavior for new submissions.
        </Card.Description>
      </Card.Header>
      <Card.Content>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <Checkbox.Root
            isSelected={settings.auto_publish_default}
            onChange={(checked) => setSettings({ ...settings, auto_publish_default: checked })}
          >
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              Auto-publish new submissions by default
            </Checkbox.Content>
          </Checkbox.Root>

          <TextField
            value={settings.business_name}
            onChange={(value) => setSettings({ ...settings, business_name: value })}
            isRequired
            fullWidth
          >
            <Label>Business name</Label>
            <Input />
          </TextField>

          <TextField
            value={settings.business_contact ?? ""}
            onChange={(value) => setSettings({ ...settings, business_contact: value })}
            fullWidth
          >
            <Label>Contact info (shown on reports)</Label>
            <Input />
          </TextField>

          <TextField
            value={settings.disclaimer_text}
            onChange={(value) => setSettings({ ...settings, disclaimer_text: value })}
            fullWidth
          >
            <Label>Report disclaimer</Label>
            <TextArea rows={4} />
          </TextField>

          <Button type="submit" variant="primary" isDisabled={saving} fullWidth>
            {saving ? "Saving…" : "Save settings"}
          </Button>
        </form>
      </Card.Content>
    </Card>
  );
}

export default function AdminSettingsPage() {
  return (
    <RequireAuth role="operator">
      <SettingsForm />
    </RequireAuth>
  );
}
