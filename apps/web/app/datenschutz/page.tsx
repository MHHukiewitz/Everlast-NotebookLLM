import { SiteFooter } from "@/components/SiteFooter";
import { t } from "@/lib/i18n";
import { operator } from "@/lib/operator";

export default function DatenschutzPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 text-sm leading-6">
        <a className="text-accent" href="/">
          ← {t.product}
        </a>
        <h1 className="mt-4 text-2xl font-medium">Datenschutzerklärung</h1>
        <p className="mt-4 text-neutral-600">Diese Erklärung gilt für die öffentliche Demo. Sie ist kein Rechtsrat.</p>

        <h2 className="mt-6 font-medium">Verantwortliche Stelle</h2>
        <p>
          {operator.name}
          <br />
          {operator.address}
          <br />
          E-Mail: {operator.email}
        </p>

        <h2 className="mt-6 font-medium">Welche Daten wir verarbeiten</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Konto: E-Mail und Passwort-Hash</li>
          <li>Notebook-Inhalte: Quellen, Dateien, Chat, Notizen, Einbettungen, Recherche</li>
          <li>Sitzungs-Cookie für die Anmeldung</li>
          <li>Technische Serverprotokolle, zum Beispiel IP-Adresse und Zeitpunkt</li>
        </ul>

        <h2 className="mt-6 font-medium">Zweck und Rechtsgrundlage</h2>
        <p>
          Wir verarbeiten die Daten, damit du das Notebook nutzen kannst. Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO
          (Vertrag bzw. vorvertragliche Nutzung). Die Registrierung ist auf eine E-Mail-Liste beschränkt.
          E-Mail-Adressen werden in dieser Demo nicht bestätigt.
        </p>

        <h2 className="mt-6 font-medium">Cookies</h2>
        <p>
          Die Demo setzt ein httpOnly-Sitzungs-Cookie namens <code>session</code>. Das Cookie ist für die Anmeldung
          erforderlich (TTDSG § 25). Es gibt keine Analyse-Cookies und kein Tracking. Deshalb gibt es kein
          Cookie-Banner.
        </p>

        <h2 className="mt-6 font-medium">Modellrouten und Auftragsverarbeitung</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Lokal (Ollama): Anfrage und Treffer bleiben auf der Maschine.</li>
          <li>EU-Gateway: nur bei Bestätigung. Es braucht einen AVV / DPA.</li>
          <li>OpenRouter: nur bei Bestätigung. Demo, in der Regel kein EU-Standort.</li>
        </ul>
        <p className="mt-2">Einbettungen verlassen die Maschine nicht. Wir trainieren keine Modelle mit deinen Daten.</p>

        <h2 className="mt-6 font-medium">Speicherdauer</h2>
        <p>
          Konten und Notebooks bleiben bis zur Löschung. Recherche-Zwischendaten: 30 Tage.
        </p>

        <h2 className="mt-6 font-medium">Rechte</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Export: Notebook als JSON</li>
          <li>Löschen: einzelnes Notebook oder das eigene Konto</li>
          <li>Das vorbereitete Demo-Konto kann nicht gelöscht werden</li>
        </ul>
      </main>
      <SiteFooter extra={t.footer} />
    </div>
  );
}
