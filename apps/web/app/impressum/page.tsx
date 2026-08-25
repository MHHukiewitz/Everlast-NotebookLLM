import { SiteFooter } from "@/components/SiteFooter";
import { t } from "@/lib/i18n";
import { operator } from "@/lib/operator";

export default function ImpressumPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 text-sm leading-6">
        <a className="text-accent" href="/">
          ← {t.product}
        </a>
        <h1 className="mt-4 text-2xl font-medium">{t.impressum}</h1>
        <p className="mt-4">Diese Seite ist ein öffentliches Demo-Angebot.</p>
        <p className="mt-3">
          {operator.name}
          <br />
          {operator.address}
          <br />
          E-Mail: {operator.email}
        </p>
      </main>
      <SiteFooter extra={t.footer} />
    </div>
  );
}
