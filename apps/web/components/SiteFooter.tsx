import { t } from "@/lib/i18n";

export function SiteFooter({ extra }: { extra?: string }) {
  return (
    <footer className="border-t border-line px-4 py-2 text-center text-[11px] text-neutral-500">
      {extra ? <p>{extra}</p> : null}
      <p className="mt-1 flex justify-center gap-3">
        <a className="underline" href="/impressum">
          {t.impressum}
        </a>
        <a className="underline" href="/datenschutz">
          {t.privacy}
        </a>
      </p>
    </footer>
  );
}
