"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Card, Checkbox, Input, Label, TextArea, TextField } from "@heroui/react";
import Button from "@/components/Button";
import RequireAuth from "@/components/RequireAuth";
import Skeleton from "@/components/Skeleton";
import ErrorState from "@/components/ErrorState";
import { useAuth } from "@/lib/auth-context";
import { useBranding } from "@/lib/branding-context";
import { toastError, toastSuccess } from "@/lib/toast";
import * as api from "@/lib/api";

/** Groups the form's fields so it doesn't read as one long undifferentiated
 *  column now that contact and social details live here too. */
function SectionHeading({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mt-2 border-t border-border pt-4">
      <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      <p className="text-xs text-muted">{hint}</p>
    </div>
  );
}

function SettingsForm() {
  const { token } = useAuth();
  const { refresh: refreshBranding } = useBranding();
  const [settings, setSettings] = useState<api.Settings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    setLoadError(null);
    api
      .getSettings(token)
      .then(setSettings)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load settings"));
  }, [token]);

  useEffect(load, [load]);

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
      <div className="mx-auto max-w-2xl">
        <ErrorState message={loadError} onRetry={load} />
      </div>
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
          Branding shown on reports, the contact details and social links published on the public
          site, and the default auto-publish behavior for new submissions.
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

          <SectionHeading
            title="Contact details"
            hint="Shown on the public contact page and in the site footer. Leave a field blank to hide it."
          />

          <TextField
            value={settings.contact_email ?? ""}
            onChange={(value) => setSettings({ ...settings, contact_email: value })}
            type="email"
            fullWidth
          >
            <Label>Public email address</Label>
            <Input />
          </TextField>

          <TextField
            value={settings.contact_location ?? ""}
            onChange={(value) => setSettings({ ...settings, contact_location: value })}
            fullWidth
          >
            <Label>Service area</Label>
            <Input />
          </TextField>

          {/* A number rather than a sentence: the site is bilingual, and the
              surrounding wording lives in the translation files so it stays
              correct in both languages. Blank hides the line entirely. */}
          <TextField
            value={
              settings.contact_response_days === null ? "" : String(settings.contact_response_days)
            }
            onChange={(value) =>
              setSettings({
                ...settings,
                contact_response_days: value.trim() === "" ? null : Number(value),
              })
            }
            type="number"
            fullWidth
          >
            <Label>Usual reply time (working days)</Label>
            <Input />
          </TextField>

          <Checkbox.Root
            isSelected={settings.contact_in_person}
            onChange={(checked) => setSettings({ ...settings, contact_in_person: checked })}
          >
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              Offer handover in person by arrangement
            </Checkbox.Content>
          </Checkbox.Root>

          <SectionHeading
            title="Social links"
            hint="Full https:// profile addresses. Anything left blank simply doesn't appear."
          />

          <TextField
            value={settings.social_instagram ?? ""}
            onChange={(value) => setSettings({ ...settings, social_instagram: value })}
            fullWidth
          >
            <Label>Instagram URL</Label>
            <Input />
          </TextField>

          <TextField
            value={settings.social_facebook ?? ""}
            onChange={(value) => setSettings({ ...settings, social_facebook: value })}
            fullWidth
          >
            <Label>Facebook URL</Label>
            <Input />
          </TextField>

          <TextField
            value={settings.social_x ?? ""}
            onChange={(value) => setSettings({ ...settings, social_x: value })}
            fullWidth
          >
            <Label>X (Twitter) URL</Label>
            <Input />
          </TextField>

          {/* A number, not a link -- the site builds the wa.me address from it,
              which keeps a pasted URL out of the page's markup entirely. */}
          <TextField
            value={settings.social_whatsapp ?? ""}
            onChange={(value) => setSettings({ ...settings, social_whatsapp: value })}
            fullWidth
          >
            <Label>WhatsApp number (international, e.g. 35054000000)</Label>
            <Input />
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
