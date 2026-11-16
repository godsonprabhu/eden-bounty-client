import { MetadataRoute } from "next";
import { SITE_URL } from "@/config/site-url";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/login", "/admin"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
