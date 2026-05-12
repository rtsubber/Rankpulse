import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BoostRank by BrandBoost Studio — Free SEO Audits for E-Commerce",
  description: "Free SEO audits in 30 seconds. Catch broken meta tags, slow pages, and missing schema. A BrandBoost Studio product. Works with Shopify, WooCommerce, and any store.",
  openGraph: {
    title: "BoostRank by BrandBoost Studio — Free SEO Audits",
    description: "Free SEO score for your store. A BrandBoost Studio product. Catch broken tags, slow pages, and missing schema in 30 seconds.",
    type: "website",
    url: "https://boostrank.co",
  },
  twitter: {
    card: "summary_large_image",
    title: "BoostRank — Free SEO Audits by BrandBoost Studio",
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