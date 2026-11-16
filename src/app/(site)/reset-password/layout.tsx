import type { Metadata } from "next";
import { headers } from "next/headers";

export const metadata: Metadata = {
  title: "Set password",
  description: "Set or reset the password for an EDEN BOUNTY customer or investor account.",
  alternates: { canonical: "/reset-password" },
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  referrer: "no-referrer",
};

/**
 * Runs while the HTML is still being parsed, before any application JavaScript: moves the
 * single-use token out of the URL fragment into memory (never into storage) and rewrites the
 * current history entry, so the token is not left in the address bar, back/forward history or
 * session restore. The page component picks it up from memory and deletes it.
 */
const CAPTURE_TOKEN = `(function(){try{var h=location.hash;if(h&&h.indexOf('token=')>-1){var t=new URLSearchParams(h.slice(1)).get('token');if(t){Object.defineProperty(window,'__ebLinkToken',{value:t,configurable:true,writable:true});}history.replaceState(null,'',location.pathname);}}catch(e){}})();`;

export default async function Layout({ children }: { children: React.ReactNode }) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <>
      <script id="eb-link-token-capture" nonce={nonce} dangerouslySetInnerHTML={{ __html: CAPTURE_TOKEN }} />
      {children}
    </>
  );
}
