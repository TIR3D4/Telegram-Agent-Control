import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Azad Bird · Telegram Control",
  description: "Private ChatGPT connector to your Telegram publishing gateway.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
