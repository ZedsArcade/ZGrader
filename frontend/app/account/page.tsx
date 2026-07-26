"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Card, Checkbox, Description, Input, Label, TextField } from "@heroui/react";
import Button from "@/components/Button";
import ConfirmDialog from "@/components/ConfirmDialog";
import RequireAuth from "@/components/RequireAuth";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useTranslations } from "@/lib/i18n/context";
import { toastError, toastSuccess } from "@/lib/toast";

function AccountInner() {
  const { user, token, adoptToken, refreshUser, logout } = useAuth();
  const router = useRouter();
  const t = useTranslations();

  const [displayName, setDisplayName] = useState("");
  const [marketing, setMarketing] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!user) return;
    setDisplayName(user.display_name ?? "");
    setMarketing(user.marketing_consent);
  }, [user]);

  if (!user || !token) return null;

  async function handleProfile(event: FormEvent) {
    event.preventDefault();
    setSavingProfile(true);
    try {
      await api.updateProfile(token!, {
        display_name: displayName.trim() || null,
        marketing_consent: marketing,
      });
      await refreshUser();
      toastSuccess(t.account.saved);
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.account.saveFailed);
    } finally {
      setSavingProfile(false);
    }
  }

  async function handlePassword(event: FormEvent) {
    event.preventDefault();
    setChangingPassword(true);
    try {
      const { access_token } = await api.changePassword(token!, currentPassword, newPassword);
      // The server retired every token for this account, including the one
      // this tab is holding -- adopt the replacement or the next request 401s.
      await adoptToken(access_token);
      setCurrentPassword("");
      setNewPassword("");
      toastSuccess(t.account.changed);
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.account.changeFailed);
    } finally {
      setChangingPassword(false);
    }
  }

  async function handleResend() {
    try {
      await api.resendVerification(user!.email);
    } finally {
      // Same message either way -- the endpoint deliberately doesn't say
      // whether the address needed confirming.
      toastSuccess(t.account.resent);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.deleteAccount(token!);
      logout();
      router.push("/");
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.account.deleteFailed);
      setDeleting(false);
      setConfirmingDelete(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5">
      <Card>
        <Card.Header>
          <Card.Title>{t.account.title}</Card.Title>
          <Card.Description>{t.account.subtitle}</Card.Description>
        </Card.Header>
        <Card.Content>
          <form className="flex flex-col gap-4" onSubmit={handleProfile}>
            <div>
              <p className="text-sm font-medium text-foreground">{t.account.emailLabel}</p>
              <p className="text-sm text-muted">{user.email}</p>
              {!user.is_verified && (
                <div className="mt-2 rounded-lg border border-dashed border-border p-3">
                  <p className="text-sm text-muted">{t.account.unverified}</p>
                  <button
                    type="button"
                    onClick={handleResend}
                    className="mt-1 text-sm font-semibold text-accent underline-offset-2 hover:underline"
                  >
                    {t.account.resend}
                  </button>
                </div>
              )}
            </div>

            <TextField value={displayName} onChange={setDisplayName} fullWidth>
              <Label>{t.account.displayNameLabel}</Label>
              <Input />
              <Description>{t.account.displayNameHint}</Description>
            </TextField>

            <Checkbox.Root isSelected={marketing} onChange={setMarketing}>
              <Checkbox.Content>
                <Checkbox.Control>
                  <Checkbox.Indicator />
                </Checkbox.Control>
                <span className="text-sm">{t.account.marketingLabel}</span>
              </Checkbox.Content>
            </Checkbox.Root>
            <p className="text-xs text-muted">{t.account.marketingHint}</p>

            <Button type="submit" variant="primary" isDisabled={savingProfile}>
              {savingProfile ? t.account.saving : t.account.save}
            </Button>
          </form>
        </Card.Content>
      </Card>

      <Card>
        <Card.Header>
          <Card.Title>{t.account.changePasswordTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <form className="flex flex-col gap-4" onSubmit={handlePassword}>
            <TextField
              type="password"
              value={currentPassword}
              onChange={setCurrentPassword}
              isRequired
              fullWidth
            >
              <Label>{t.account.currentPassword}</Label>
              <Input />
            </TextField>
            <TextField
              type="password"
              value={newPassword}
              onChange={setNewPassword}
              isRequired
              minLength={8}
              fullWidth
            >
              <Label>{t.account.newPassword}</Label>
              <Input />
            </TextField>
            <Button type="submit" variant="primary" isDisabled={changingPassword}>
              {changingPassword ? t.account.changing : t.account.changePassword}
            </Button>
          </form>
        </Card.Content>
      </Card>

      <Card>
        <Card.Header>
          <Card.Title>{t.account.dangerTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-muted">{t.account.dangerBody}</p>
          <div className="mt-4">
            <Button
              variant="danger"
              isDisabled={deleting}
              onPress={() => setConfirmingDelete(true)}
            >
              {t.account.deleteButton}
            </Button>
          </div>
        </Card.Content>
      </Card>

      <ConfirmDialog
        open={confirmingDelete}
        title={t.account.deleteConfirmTitle}
        body={t.account.deleteConfirmBody}
        confirmLabel={t.account.deleteConfirm}
        cancelLabel={t.account.deleteCancel}
        destructive
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmingDelete(false)}
      />
    </div>
  );
}

export default function AccountPage() {
  return (
    <RequireAuth>
      <AccountInner />
    </RequireAuth>
  );
}
