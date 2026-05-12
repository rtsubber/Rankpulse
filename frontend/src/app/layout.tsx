import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RankPulse — Instant SEO Audits for E-Commerce Stores",
  description: "Catch broken meta tags, slow pages, and missing schema before Google does. Free SEO audits in 30 seconds. Works with Shopify, WooCommerce, and any store.",
  openGraph: {
    title: "RankPulse — Instant SEO Audits for E-Commerce Stores",
    description: "Free SEO score for your store. Catch broken tags, slow pages, and missing schema in 30 seconds.",
    type: "website",
    url: "https://rankpulse.co",
  },
  twitter: {
    card: "summary_large_image",
    title: "RankPulse — Instant SEO Audits",
    description: "Free SEO audit for any e-commerce store. Get your score in 30 seconds.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}