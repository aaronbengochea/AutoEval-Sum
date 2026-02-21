import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

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
      <body className="bg-zinc-950 text-zinc-100 min-h-screen">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
