"use client";

import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { Card, Checkbox, Input, Label, TextArea, TextField } from "@heroui/react";
import Button from "@/components/Button";
import RequireAuth from "@/components/RequireAuth";
import Skeleton from "@/components/Skeleton";
import ErrorState from "@/components/ErrorState";
import { useAuth } from "@/lib/auth-context";
import { useBranding } from "@/lib/branding-context";
import { toastError, toastSuccess } from "@/lib/toast";
import { useServiceImages } from "@/lib/use-service-images";
import * as api from "@/lib/api";

// Labels are hardcoded English like the rest of this operator-only screen --
// the public pages are bilingual, the admin panel is not.
const SERVICE_TIERS: { slug: api.ServiceSlug; label: string }[] = [
  { slug: "analysis", label: "Image analysis & report" },
  { slug: "subscription", label: "Unlimited subscription" },
  { slug: "personalised", label: "Personalised pre-grading" },
  { slug: "restoration", label: "Restorations" },
  { slug: "packaging", label: "Pre-packaging for grading" },
  { slug: "collection", label: "Collection & shipping point" },
];

function ServiceImageRow({
  slug,
  label,
  version,
  token,
  onChanged,
}: {
  slug: api.ServiceSlug;
  label: string;
  version: number | undefined;
  token: string;
  onChanged: () => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Reset first, so re-picking the same file after a failure still fires.
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      await api.uploadServiceImage(token, slug, file);
      await onChanged();
      toastSuccess(`${label} image updated.`);
    } catch (err) {
      toastError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove() {
    setBusy(true);
    try {
      await api.deleteServiceImage(token, slug);
      await onChanged();
      toastSuccess(`${label} image removed.`);
    } catch (err) {
      toastError(err instanceof Error ? err.message : "Couldn't remove the image");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-secondary p-3">
      {version === undefined ? (
        <div className="flex h-14 w-24 shrink-0 items-center justify-center rounded border border-dashed border-border text-xs text-muted">
          None
        </div>
      ) : (
        <img
          src={api.serviceImageUrl(slug, version)}
          alt=""
          className="h-14 w-24 shrink-0 rounded border border-border object-cover"
        />
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">{label}</p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={handleFile}
        className="hidden"
      />
      <Button
        variant="outline"
        size="sm"
        isDisabled={busy}
        onPress={() => inputRef.current?.click()}
      >
        {busy ? "Working…" : version === undefined ? "Add image" : "Replace"}
      </Button>
      {version !== undefined && (
        <Button variant="danger-soft" size="sm" isDisabled={busy} onPress={handleRemove}>
          Remove
        </Button>
      )}
    </div>
  );
}

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

function GradingCompanyRows({
  token,
  onChanged,
}: {
  token: string;
  onChanged: () => Promise<void>;
}) {
  const [companies, setCompanies] = useState<api.GradingCompanyStatus[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api.getGradingCompanies(token).then(setCompanies).catch(() => setCompanies([]));
  }, [token]);

  async function toggle(company: string, active: boolean) {
    setBusy(company);
    try {
      const updated = await api.setGradingCompanyActive(token, company, active);
      setCompanies((prev) =>
        (prev ?? []).map((c) => (c.company === company ? { ...c, active: updated.active } : c))
      );
      // The public copy names the enabled companies, so refresh branding or
      // the landing page keeps the old list until a reload.
      await onChanged();
      toastSuccess(`${company} ${active ? "enabled" : "disabled"}.`);
    } catch (err) {
      toastError(err instanceof Error ? err.message : "Couldn't update the company");
    } finally {
      setBusy(null);
    }
  }

  if (companies === null) return <Skeleton className="h-24 w-full" />;

  return (
    <div className="flex flex-col gap-2">
      {companies.map(({ company, active }) => (
        <div
          key={company}
          className="flex items-center gap-3 rounded-lg border border-border bg-surface-secondary p-3"
        >
          <Checkbox.Root
            isSelected={active}
            isDisabled={busy === company}
            onChange={(checked) => toggle(company, checked)}
          >
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              {company}
            </Checkbox.Content>
          </Checkbox.Root>
          {!active && <span className="ml-auto text-xs text-muted">Not compared</span>}
        </div>
      ))}
    </div>
  );
}

function SettingsForm() {
  const { token } = useAuth();
  const { refresh: refreshBranding } = useBranding();
  const { images: serviceImages, refresh: refreshServiceImages } = useServiceImages();
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
            <Label>Business name (analysis side, and the legal name on reports)</Label>
            <Input />
          </TextField>

          <TextField
            value={settings.care_business_name}
            onChange={(value) => setSettings({ ...settings, care_business_name: value })}
            isRequired
            fullWidth
          >
            <Label>Care brand name (the /care section)</Label>
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

          <SectionHeading
            title="Service images"
            hint="A banner shown on each card on the public Services page. These upload straight away — the Save button below does not apply to them."
          />

          <div className="flex flex-col gap-2">
            {SERVICE_TIERS.map(({ slug, label }) => (
              <ServiceImageRow
                key={slug}
                slug={slug}
                label={label}
                version={serviceImages[slug]}
                token={token ?? ""}
                onChanged={refreshServiceImages}
              />
            ))}
          </div>

          <SectionHeading
            title="Grading companies"
            hint="Which companies appear in the comparison. Applies immediately, and the public site names only the enabled ones. Reports already generated keep their existing companies until that card is re-analysed — which includes a client dismissing one of its findings."
          />

          <GradingCompanyRows token={token ?? ""} onChanged={refreshBranding} />

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
