"use client";

import { type FormEvent, useState } from "react";
import { SiteFooter } from "@/components/SiteFooter";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [privacyAck, setPrivacyAck] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const user = await api.register(email, password, privacyAck).catch((err: Error) => {
      setError(err.message);
      return null;
    });
    setBusy(false);
    if (user) {
      window.location.replace("/");
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-10">
        <h1 className="text-2xl font-medium">{t.product}</h1>
        <p className="mt-1 text-sm text-neutral-500">{t.register}</p>
        <p className="mt-3 text-sm text-neutral-600">{t.registerHint}</p>
        <form className="mt-6 space-y-3" onSubmit={onSubmit}>
          <label className="block text-sm">
            {t.email}
            <input
              className="mt-1 w-full rounded-lg border border-line px-3 py-2"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="block text-sm">
            {t.password}
            <input
              className="mt-1 w-full rounded-lg border border-line px-3 py-2"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input
              className="mt-1"
              type="checkbox"
              checked={privacyAck}
              onChange={(e) => setPrivacyAck(e.target.checked)}
              required
            />
            <span>
              {t.privacyAck}{" "}
              <a className="text-accent underline" href="/datenschutz">
                {t.privacy}
              </a>
            </span>
          </label>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <button className="btn-primary w-full" disabled={busy} type="submit">
            {t.register}
          </button>
        </form>
        <p className="mt-4 text-sm text-neutral-600">
          {t.hasAccount}{" "}
          <a className="text-accent underline" href="/login">
            {t.login}
          </a>
        </p>
      </main>
      <SiteFooter extra={t.footer} />
    </div>
  );
}
