import { SiteConfig } from "@/types";

export const siteConfig: SiteConfig = {
  name: "EDEN BOUNTY",
  legalName: "EDEN BOUNTY Sdn. Bhd.",
  country: "Malaysia",
  headquarters: "Malaysia",
  description:
    "Malaysia-based wholesale trading and business solutions company operating across its commercial services.",
  timezone: "Asia/Kuala_Lumpur",
  contact: {
    email: "info@edenbounty.org",
    registrationNumber: "202501058702 (1660108-D)",
    address: "MRI-1409, Sri Acappella, Jalan 13/33, Section 13, Shah Alam, 40100, Selangor, Malaysia",
    // Internal mail-hosting details are intentionally NOT kept here: this config ships in the public JS bundle.
  },
  mainNav: [
    {
      title: "Company Overview",
      href: "#overview",
      description: "Corporate identity, business philosophy, and commercial trading scope.",
    },
    {
      title: "Trading Services",
      href: "/services",
      description: "Detailed overview of our commercial trading services.",
    },
    {
      title: "Supply Chain",
      href: "#capabilities",
      description: "Commercial sourcing and trade coordination.",
    },
    {
      title: "Drone",
      href: "#agritech",
      description: "Commercial service dedicated to drone trading.",
    },
    {
      title: "Governance",
      href: "#governance",
      description: "Corporate governance, commercial standards, and trade documentation.",
    },
    {
      title: "Trade Inquiry",
      href: "#inquiry",
      description: "Official commercial contact and inquiry preparation.",
    },
  ],
  overview: {
    headline: "Wholesale Trading & Commercial Business Solutions",
    subheadline: "Based in Malaysia, operating across its commercial services.",
    summary:
      "EDEN BOUNTY Sdn. Bhd. is a Malaysia-based wholesale trading and business solutions company operating across its commercial services.",
    pillars: [
      {
        title: "Wholesale Trading Focus",
        description:
          "Structured for commercial trading activities across diverse business sectors.",
      },
      {
        title: "Commercial Services",
        description:
          "A unified commercial enterprise managing distinct business sectors.",
      },
      {
        title: "Commercial Governance",
        description:
          "Committed to professional business communication and formal commercial terms.",
      },
    ],
  },
  supplyChain: {
    title: "Commercial Sourcing & Trade Coordination",
    description:
      "Coordinating commercial communications and trade inquiries across our business services.",
    capabilities: [
      {
        title: "Commercial Sourcing",
        description:
          "Managing commercial relationships and trade inquiries for confirmed business services.",
        iconName: "Globe",
      },
      {
        title: "Trade Coordination",
        description:
          "Coordinating commercial trade inquiries and business correspondence.",
        iconName: "Layers",
      },
      {
        title: "Trade Documentation",
        description:
          "Maintaining formal documentation and commercial terms for trade correspondence.",
        iconName: "FileCheck",
      },
    ],
  },
  agriTech: {
    title: "Drone Commercial Trading",
    description:
      "EDEN BOUNTY Sdn. Bhd. presents drone products as part of its commercial trading interests.",
    summary:
      "EDEN BOUNTY Sdn. Bhd. presents drone products as part of its commercial trading interests.",
    features: [
      {
        title: "UAV Platforms",
        description:
          "Drone products presented as part of our commercial trading interests.",
      },
      {
        title: "Manufacturer Product Information",
        description:
          "Available manufacturer technical specifications provided upon enquiry.",
      },
      {
        title: "Commercial Trading Inquiries",
        description:
          "Commercial trading inquiries and business correspondence managed directly via official business email.",
      },
    ],
  },
  compliance: {
    title: "Corporate Governance & Business Standards",
    description:
      "Operating with transparent business information, professional trade conduct, and clear communication.",
    statement:
      "EDEN BOUNTY Sdn. Bhd. presents its corporate identity and commercial activities through clear business information and direct commercial communication.",
    notes: [
      "Commercial enquiry intake and preliminary review across our services.",
      "Commercial quotations upon request, subject to review.",
      "Transaction terms discussed and mutually agreed before proceeding.",
      "Direct business correspondence via our official business email.",
    ],
  },
};
