import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "UrbanGuard",
  description: "Real-time city safety intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
