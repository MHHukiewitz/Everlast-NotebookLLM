import type { Metadata } from "next";
import "./globals.css";
import { t } from "@/lib/i18n";

export const metadata: Metadata = {
  title: t.product,
  description: "Source-grounded research notebook",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
