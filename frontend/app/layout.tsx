import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "pronoturf — le turf, en clair",
  description: "Plateforme locale de pronostic hippique",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className="h-full antialiased">
      <body className="min-h-full bg-white text-slate-900 flex flex-col">{children}</body>
    </html>
  );
}
