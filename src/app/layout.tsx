import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { Instrument_Serif, Manrope, JetBrains_Mono } from "next/font/google";
import { ThemeProvider } from "@/context/ThemeContext";
import { GlobalUIStateProvider } from "@/context/GlobalUIStateContext";
import {
  GlobalOfflineBanner,
  ToastContainer,
  SessionExpiredModal,
} from "@/components/ui/states";
import "./globals.css";
import { SITE_URL } from "@/config/site-url";
import { siteConfig } from "@/config/site";

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  variable: "--ff-serif",
  display: "swap",
  weight: ["400"],
  style: ["normal", "italic"],
});

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--ff-sans",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--ff-mono",
  display: "swap",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "EDEN BOUNTY Sdn. Bhd. | Wholesale Trading & Business Solutions",
    template: "%s | EDEN BOUNTY Sdn. Bhd.",
  },
  description:
    "EDEN BOUNTY Sdn. Bhd. (202501058702) is a Malaysia-based wholesale trading and business solutions company operating across commercial services including mineral water, scrap trading, construction / building promotion, petroleum products, furnace oil, and drone solutions.",
  keywords: [
    "Eden Bounty",
    "EDEN BOUNTY Sdn. Bhd.",
    "wholesale trading Malaysia",
    "Malaysia commercial procurement",
    "petroleum products wholesale",
    "furnace oil trading",
    "scrap metal trading Malaysia",
    "construction materials wholesale",
    "drones Malaysia",
    "mineral water wholesale",
    "building promotion",
    "B2B commercial trade Malaysia",
  ],
  authors: [{ name: "EDEN BOUNTY Sdn. Bhd.", url: SITE_URL }],
  creator: "EDEN BOUNTY Sdn. Bhd.",
  publisher: "EDEN BOUNTY Sdn. Bhd.",
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "en_MY",
    url: SITE_URL,
    siteName: "EDEN BOUNTY Sdn. Bhd.",
    title: "EDEN BOUNTY Sdn. Bhd. | Wholesale Trading & Business Solutions",
    description:
      "Malaysia-based wholesale trading enterprise operating across its commercial divisions.",
    images: [
      {
        url: "/images/hero/hero-industrial.jpg",
        width: 1200,
        height: 630,
        alt: "Eden Bounty Corporate Wholesale Trading & Solutions",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "EDEN BOUNTY Sdn. Bhd. | Wholesale Trading & Business Solutions",
    description:
      "Malaysia-based wholesale trading enterprise operating across its commercial divisions.",
    images: ["/images/hero/hero-industrial.jpg"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
    apple: "/icon.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#07090c",
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Per-request CSP nonce set by src/proxy.ts (reading it also makes every page render per request).
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html
      lang="en"
      suppressHydrationWarning
      data-scroll-behavior="smooth"
      className={`${instrumentSerif.variable} ${manrope.variable} ${jetbrainsMono.variable} dark`}
      data-theme="dark"
    >
      <head>
        <script
          type="application/ld+json"
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "Organization",
              name: siteConfig.legalName,
              alternateName: siteConfig.name,
              url: SITE_URL,
              email: siteConfig.contact.email,
              identifier: siteConfig.contact.registrationNumber,
              address: {
                "@type": "PostalAddress",
                streetAddress: "MRI-1409, Sri Acappella, Jalan 13/33, Section 13",
                addressLocality: "Shah Alam",
                postalCode: "40100",
                addressRegion: "Selangor",
                addressCountry: "MY",
              },
            }),
          }}
        />
        <script
          id="eb-theme-init"
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var q=new URLSearchParams(location.search).get('theme');if(q==='light'||q==='dark'){localStorage.setItem('eb_theme',q);}var s=localStorage.getItem('eb_theme');var t=(s==='light')?'light':'dark';var r=document.documentElement;r.classList.remove('light','dark');r.classList.add(t);r.setAttribute('data-theme',t);r.style.colorScheme=t;}catch(e){document.documentElement.classList.add('dark');document.documentElement.setAttribute('data-theme','dark');}})();`,
          }}
        />
      </head>
      <body className="min-h-screen bg-paper text-ink antialiased">
        <ThemeProvider>
          <GlobalUIStateProvider>
            <GlobalOfflineBanner />
            <ToastContainer />
            <SessionExpiredModal />
            {children}
          </GlobalUIStateProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
