/** Types for the customer portal, investor portal and their admin management screens. */

export type PortalRole = "CUSTOMER" | "INVESTOR";

export interface PortalUser {
  id: string;
  email: string;
  role: PortalRole;
  full_name: string;
  company_name: string | null;
  contact_number: string | null;
  country: string | null;
}

export interface PortalMe extends PortalUser {
  last_login_at: string | null;
  csrf_token: string;
}

export interface DivisionRef {
  id: string;
  code: string;
  name: string;
}

export interface ShipmentEvent {
  id: string;
  description: string;
  location: string | null;
  occurred_at: string;
}

export interface Shipment {
  id: string;
  carrier: string | null;
  tracking_number: string | null;
  origin: string | null;
  destination: string | null;
  status: string;
  shipped_at: string | null;
  estimated_delivery_on: string | null;
  delivered_at: string | null;
  events: ShipmentEvent[];
}

export interface OrderStatusEvent {
  old_status: string | null;
  new_status: string;
  note: string | null;
  created_at: string;
}

export interface OrderSummary {
  id: string;
  reference_number: string;
  division: DivisionRef;
  product_description: string;
  quantity: string | null;
  unit_of_measurement: string | null;
  total_amount: string | null;
  currency: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface OrderDetail extends OrderSummary {
  customer_note: string | null;
  enquiry_reference: string | null;
  status_history: OrderStatusEvent[];
  shipments: Shipment[];
}

export interface AdminOrderSummary extends OrderSummary {
  customer: PortalUser;
}

export interface AdminOrderDetail extends OrderDetail {
  customer: PortalUser;
  enquiry_id: string | null;
}

export interface CustomerEnquirySummary {
  id: string;
  reference_number: string;
  division: DivisionRef;
  product_focus: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface EnquiryUpdate {
  kind: "STATUS" | "MESSAGE";
  text: string;
  created_at: string;
}

export interface CustomerEnquiryDetail extends CustomerEnquirySummary {
  quantity: string | null;
  unit_of_measurement: string | null;
  specifications: string | null;
  additional_notes: string | null;
  preferred_incoterm: string | null;
  target_destination_port: string | null;
  updates: EnquiryUpdate[];
  orders: OrderSummary[];
}

export interface CustomerOverview {
  enquiries_total: number;
  enquiries_open: number;
  orders_total: number;
  orders_active: number;
  recent_enquiries: CustomerEnquirySummary[];
  recent_orders: OrderSummary[];
}

export interface Investment {
  id: string;
  reference_number: string;
  division: DivisionRef;
  amount: string;
  currency: string;
  invested_on: string;
  status: string;
  summary: string | null;
  created_at: string;
}

export interface AdminInvestment extends Investment {
  investor: PortalUser;
}

export interface CurrencyTotal {
  currency: string;
  total: string;
  active_total: string;
}

export interface DivisionAllocation {
  division: DivisionRef;
  currency: string;
  amount: string;
  share_percent: string;
  investments: number;
}

export interface InvestorOverview {
  totals: CurrencyTotal[];
  investments_count: number;
  status_counts: Record<string, number>;
  allocation: DivisionAllocation[];
  recent_investments: Investment[];
}

export interface InvestorDocument {
  id: string;
  title: string;
  category: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  is_published: boolean;
  published_at: string | null;
  created_at: string;
}

export interface InvestorUpdate {
  id: string;
  investor_id: string | null;
  title: string;
  body: string;
  is_published: boolean;
  published_at: string | null;
  created_at: string;
}

export interface PortalUserAdmin extends PortalUser {
  is_active: boolean;
  /** True until the account holder sets their own password from the invitation link. */
  invitation_pending: boolean;
  last_login_at: string | null;
  locked_until: string | null;
  created_at: string;
}

/** A newly issued invitation or reset link. `link` is present only for MANUAL delivery, shown once. */
export interface PasswordLink {
  purpose: "INVITE" | "RESET";
  delivery: "EMAIL" | "MANUAL";
  /** SENT: accepted by the mail server. FAILED: not sent, link revoked. SHOWN_ONCE: MANUAL delivery. */
  delivery_status: "SENT" | "FAILED" | "SHOWN_ONCE" | "PENDING";
  expires_at: string;
  link: string | null;
}

export interface PortalUserCreated extends PortalUserAdmin {
  invitation: PasswordLink;
}

export interface AdminEnquiryRef {
  id: string;
  reference_number: string;
  company_name: string;
  product_focus: string;
  status: string;
  created_at: string;
}

export interface PortalUserAdminDetail extends PortalUserAdmin {
  /** Newest link that can still be used (metadata only, never the link). */
  active_link: { purpose: "INVITE" | "RESET"; created_at: string; expires_at: string } | null;
  /** Latest forgot-password request recorded while email delivery was unavailable. */
  reset_requested_at: string | null;
  /** Outcome of the most recent link email (last 7 days). FAILED means that link was revoked. */
  last_link_email: { status: "SENT" | "FAILED"; at: string } | null;
  enquiries: AdminEnquiryRef[];
  orders: OrderSummary[];
  investments: Investment[];
  documents: InvestorDocument[];
}

export interface PortalSummary {
  total_customers: number;
  total_investors: number;
  total_enquiries: number;
  total_orders: number;
  orders_by_status: Record<string, number>;
  investment_totals: CurrencyTotal[] | null;
  investments_count: number | null;
}

export const ORDER_STATUSES = ["CONFIRMED", "PROCESSING", "READY_TO_SHIP", "SHIPPED", "IN_TRANSIT", "DELIVERED", "COMPLETED", "CANCELLED"] as const;
export const SHIPMENT_STATUSES = ["PREPARING", "SHIPPED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "RETURNED"] as const;
export const INVESTMENT_STATUSES = ["PENDING", "ACTIVE", "MATURED", "EXITED", "CANCELLED"] as const;
export const DOCUMENT_CATEGORIES = ["FINANCIAL_REPORT", "INVESTMENT_DOCUMENT", "OTHER"] as const;
