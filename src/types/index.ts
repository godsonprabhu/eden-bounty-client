export interface NavItem {
  title: string;
  href: string;
  description?: string;
  isExternal?: boolean;
}

export interface ServiceSpecItem {
  label: string;
  value: string;
}

export interface DivisionSubcategory {
  title: string;
  description?: string;
  items?: string[];
  specs?: ServiceSpecItem[];
  benefits?: string[];
}

export interface DivisionItem {
  id: string;
  code: string;
  name: string;
  sector: string;
  accentColor: string;
  description: string;
  scopeFocus: string;
  image: string;
  images?: string[];
  href: string;
  highlights?: string[];
  capabilities?: string[];
  specifications?: ServiceSpecItem[];
  applications?: string[];
  productOfferings?: string[];
  packagingOptions?: string[];
  targetCustomers?: string[];
  subcategories?: DivisionSubcategory[];
  handlingNotes?: string;
  usageDirections?: string;
  ingredients?: string[];
  /** `false` hides the division from the public site and RFQ form. The record is kept for historical enquiries. */
  active?: boolean;
}

export interface ContactConfig {
  email: string;
  /** Internal infrastructure reference for administrative webmail access (e.g. Hostinger Webmail) */
  webmailUrl?: string;
  /** Internal email hosting infrastructure provider */
  emailProvider?: string;
  /** Optional configurable unconfirmed fields (kept optional to avoid fabricated data) */
  phone?: string;
  address?: string;
  registrationNumber?: string;
}

export interface CompanyOverviewConfig {
  headline: string;
  subheadline: string;
  summary: string;
  pillars: {
    title: string;
    description: string;
  }[];
}

export interface SupplyChainConfig {
  title: string;
  description: string;
  capabilities: {
    title: string;
    description: string;
    iconName: string;
  }[];
}

export interface AgriTechConfig {
  title: string;
  description: string;
  summary: string;
  features: {
    title: string;
    description: string;
  }[];
}

export interface ComplianceConfig {
  title: string;
  description: string;
  statement: string;
  notes: string[];
}

export interface SiteConfig {
  name: string;
  legalName: string;
  country: string;
  headquarters: string;
  description: string;
  timezone: string;
  contact: ContactConfig;
  mainNav: NavItem[];
  overview: CompanyOverviewConfig;
  supplyChain: SupplyChainConfig;
  agriTech: AgriTechConfig;
  compliance: ComplianceConfig;
}
