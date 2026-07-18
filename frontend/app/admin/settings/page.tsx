"use client";

import { useEffect, useState, type FormEvent } from "react";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

function SettingsForm() {
  const { token } = useAuth();
  const [settings, setSettings] = useState<api.Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) return;
    api
      .getSettings(token)
      .then(setSettings)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load settings"));
  }, [token]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token || !settings) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.updateSettings(token, settings);
      setSettings(updated);
      setMessage("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  if (error && !settings) return <div className="alert alert-error">{error}</div>;
  if (!settings) return <p className="spinner-text">Loading…</p>;

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <div className="page-header">
        <h1>Business settings</h1>
        <p>Branding shown on reports and the default auto-publish behavior for new submissions.</p>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}
      <form className="stack" style={{ maxWidth: "none" }} onSubmit={handleSubmit}>
        <div className="checkbox-row">
          <input
            id="auto-publish-default"
            type="checkbox"
            checked={settings.auto_publish_default}
            onChange={(e) => setSettings({ ...settings, auto_publish_default: e.target.checked })}
          />
          <label htmlFor="auto-publish-default" style={{ margin: 0 }}>
            Auto-publish new submissions by default
          </label>
        </div>
        <div>
          <label htmlFor="business-name">Business name</label>
          <input
            id="business-name"
            type="text"
            value={settings.business_name}
            onChange={(e) => setSettings({ ...settings, business_name: e.target.value })}
          />
        </div>
        <div>
          <label htmlFor="business-contact">Contact info (shown on reports)</label>
          <input
            id="business-contact"
            type="text"
            value={settings.business_contact ?? ""}
            onChange={(e) => setSettings({ ...settings, business_contact: e.target.value })}
          />
        </div>
        <div>
          <label htmlFor="disclaimer">Report disclaimer</label>
          <textarea
            id="disclaimer"
            rows={4}
            value={settings.disclaimer_text}
            onChange={(e) => setSettings({ ...settings, disclaimer_text: e.target.value })}
          />
        </div>
        <button className="btn" type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>
      </form>
    </div>
  );
}

export default function AdminSettingsPage() {
  return (
    <RequireAuth role="operator">
      <SettingsForm />
    </RequireAuth>
  );
}
