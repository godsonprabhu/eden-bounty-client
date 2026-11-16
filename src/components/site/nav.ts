import { businessDivisions } from "@/data/divisions";

export type NavVariant = "link" | "outline" | "primary";

export interface NavLink {
  title: string;
  href: string;
  description?: string;
}

export interface NavColumn {
  heading: string;
  links: NavLink[];
}

export interface NavMenuItem {
  title: string;
  href: string;
  index: string;
  /** Short line shown on the left of the mega-menu panel. */
  intro?: string;
  /** Items without columns are plain links (no dropdown panel). */
  columns?: NavColumn[];
}

/** Canonical route of the Request for Quotation page. "Contact" always leads here. */
export const RFQ_HREF = "/rfq";

/** Splits the active services (single source of truth: data/divisions.ts) into menu columns. */
function divisionColumns(perColumn = 4): NavColumn[] {
  const columns: NavColumn[] = [];
  for (let i = 0; i < businessDivisions.length; i += perColumn) {
    columns.push({
      heading: i === 0 ? "Commercial services" : " ",
      links: businessDivisions.slice(i, i + perColumn).map((d) => ({
        title: d.name,
        href: `/services/${d.id}`,
      })),
    });
  }
  return columns;
}

export const SITE_MENU: NavMenuItem[] = [
  { title: "Home", href: "/", index: "00" },
  {
    title: "About",
    href: "/about",
    index: "01",
    intro: "Who we are, how we are organised and the standards we trade by.",
    columns: [
      {
        heading: "The company",
        links: [
          { title: "Company Overview", href: "/about#overview", description: "The registered entity and what it does" },
          { title: "Vision & Mission", href: "/about#vision-mission", description: "What we work towards" },
        ],
      },
      {
        heading: "Organisation",
        links: [
          { title: "Management / Leadership", href: "/about#leadership", description: "How the company is directed" },
          { title: "Company Structure", href: "/about#structure", description: "Corporate record and services" },
        ],
      },
    ],
  },
  {
    title: "Services",
    href: "/services",
    index: "02",
    intro: "Wholesale trading organised into commercial services, handled through one commercial desk.",
    columns: [
      ...divisionColumns(),
      {
        heading: "Enquiries",
        links: [
          { title: "All services", href: "/services", description: "Overview of every active service" },
          { title: "Request a quotation", href: RFQ_HREF, description: "Send an RFQ for the right service" },
        ],
      },
    ],
  },
  {
    title: "Investors",
    href: "/investors",
    index: "03",
    intro: "Confirmed corporate information for investors, partners and other stakeholders.",
    columns: [
      {
        heading: "Investor relations",
        links: [
          { title: "Investor Overview", href: "/investors", description: "Corporate identity and key facts" },
          { title: "Investment Information", href: "/investors#investment-information", description: "What is, and is not, published" },
          { title: "Commercial Services", href: "/investors#services", description: "Where the company trades" },
        ],
      },
      {
        heading: "Existing investors",
        links: [{ title: "Investor Login", href: "/investors/login", description: "Secure access to your investor dashboard" }],
      },
    ],
  },
];

/** Action buttons shown beside the menu. */
export const SITE_ACTIONS: Array<{ title: string; href: string; variant: Exclude<NavVariant, "link"> }> = [
  { title: "Login", href: "/login", variant: "outline" },
  { title: "Contact", href: RFQ_HREF, variant: "primary" },
];

/** Flat list used by the footer. */
export const SITE_NAV: Array<{ title: string; href: string; index: string; variant: NavVariant }> = [
  ...SITE_MENU.map((m) => ({ title: m.title, href: m.href, index: m.index, variant: "link" as const })),
  { title: "Login", href: "/login", index: "04", variant: "outline" },
  { title: "Contact", href: RFQ_HREF, index: "05", variant: "primary" },
];
