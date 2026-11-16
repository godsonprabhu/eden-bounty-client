import { MetadataRoute } from "next";
import { SITE_URL } from "@/config/site-url";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = SITE_URL;
  const lastModified = new Date().toISOString();
  return ["", "/about", "/services", "/investors", "/rfq"].map((path) => ({
    url: `${baseUrl}${path}`,
    lastModified,
    changeFrequency: "monthly" as const,
    priority: path === "" ? 1 : 0.8,
  }));
}
