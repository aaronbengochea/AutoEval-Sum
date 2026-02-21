import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AutoEval-Sum",
  description: "Autonomous evaluation suite improvement for summarization testing",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
