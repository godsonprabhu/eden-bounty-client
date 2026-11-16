"use client";

import React, { useState, useEffect, useRef, useId, useCallback } from "react";
import { siteConfig } from "@/config/site";
import { businessDivisions } from "@/data/divisions";
import { DivisionItem } from "@/types";
import {
  Send,
  CheckCircle2,
  Copy,
  Check,
  RotateCcw,
  AlertCircle,
  Building2,
  User,
  Mail,
  FileText,
  Layers,
  Globe,
  Phone,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  ExternalLink,
  Droplets,
  Recycle,
  HardHat,
  Fuel,
  Factory,
  Plane,
  HelpCircle,
  Edit3,
  Loader2,
  WifiOff,
} from "lucide-react";
import { useNetworkStatus } from "@/hooks/useNetworkStatus";
import { useToast } from "@/hooks/useToast";
import { FormErrorSummary } from "@/components/ui/states";

export interface FormData {
  divisionId: string;
  fullName: string;
  companyName: string;
  businessEmail: string;
  contactNumber: string;
  country: string;
  productFocus: string;
  quantity: string;
  unitOfMeasurement: string;
  specifications: string;
  additionalNotes: string;
  // Backwards compatibility
  requirements?: string;
  message?: string;
}

export interface FormErrors {
  [key: string]: string | undefined;
  divisionId?: string;
  fullName?: string;
  companyName?: string;
  businessEmail?: string;
  contactNumber?: string;
  country?: string;
  productFocus?: string;
  quantity?: string;
  unitOfMeasurement?: string;
  specifications?: string;
  additionalNotes?: string;
  requirements?: string;
  message?: string;
}

export interface TradeEnquiryFormState {
  formData: FormData;
  currentStage: number;
  selectedDivision?: DivisionItem;
}

interface TradeEnquiryFormProps {
  initialDivisionId?: string;
  lockDivision?: boolean;
  onStateChange?: (state: TradeEnquiryFormState) => void;
  onSuccess?: () => void;
}

const EMAIL_REGEX =
  /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/;

function createIdempotencyKey(): string {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

// Division icon mapping matching Trading Divisions section
const DIVISION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  "mineral-water": Droplets,
  "scrap-trading": Recycle,
  construction: HardHat,
  "petroleum-products": Fuel,
  "furnace-oil": Factory,
  "agricultural-drones": Plane,
};

// Division-specific contextual placeholder & prompt guidance (non-forced, strictly authentic)
interface DivisionPromptConfig {
  productPlaceholder: string;
  quantityPlaceholder: string;
  unitPlaceholder: string;
  specPlaceholder: string;
  notesPlaceholder: string;
  guidanceNote: string;
}

const DIVISION_PROMPTS: Record<string, DivisionPromptConfig> = {
  "petroleum-products": {
    productPlaceholder: "e.g., Diesel (Euro 5), Petrol (RON 95 / 97), Kerosene, LPG, Bitumen",
    quantityPlaceholder: "e.g., 5,000 (Optional)",
    unitPlaceholder: "e.g., Metric Tonnes (MT), Litres, Drums, or Bulk Tanker",
    specPlaceholder: "Specify product grade, ASTM / EN standards, delivery quality requirements, or commercial parameters...",
    notesPlaceholder: "Target delivery terminal, bulk tanker preferences, commercial credit terms...",
    guidanceNote: "Petroleum commercial enquiries are reviewed under wholesale commodity trade terms.",
  },
  "furnace-oil": {
    productPlaceholder: "e.g., Low-Sulphur Fuel Oil (LSFO), High-Sulphur Fuel Oil (HSFO), 180 cSt / 380 cSt",
    quantityPlaceholder: "e.g., 2,000 (Optional)",
    unitPlaceholder: "e.g., Metric Tonnes (MT), ISO Tank, or Barge Load",
    specPlaceholder: "Specify viscosity grade (180 cSt, 380 cSt), sulphur limit, flash point (>= 60°C), or boiler requirements...",
    notesPlaceholder: "Industrial delivery destination, heated storage setup, supply frequency...",
    guidanceNote: "Furnace oil enquiries are coordinated for commercial boiler, kiln, and industrial heating applications.",
  },
  "scrap-trading": {
    productPlaceholder: "e.g., HMS 1 & 2, Shredded Scrap, Copper (bare bright/millberry), Aluminium, Brass",
    quantityPlaceholder: "e.g., 500 (Optional)",
    unitPlaceholder: "e.g., Metric Tonnes (MT) or Container Loads (FCL)",
    specPlaceholder: "Specify ferrous or non-ferrous grade, ISRI specification code, chemical limits, or impurity thresholds...",
    notesPlaceholder: "Discharge port, containerized or breakbulk shipping, inspection requirements, payment terms...",
    guidanceNote: "Scrap trading enquiries are reviewed under recognised scrap specifications with weighbridge certificates.",
  },
  "agricultural-drones": {
    productPlaceholder: "e.g., Agricultural Drones (10L-40L tank), Surveillance Drones (4K optical zoom, thermal)",
    quantityPlaceholder: "e.g., 5 (Optional)",
    unitPlaceholder: "e.g., Units, Complete Sets, or Spare Modules",
    specPlaceholder: "Specify drone type (agricultural or surveillance), payload/tank capacity, optical/thermal camera requirements, RTK precision...",
    notesPlaceholder: "Commercial deployment location, spare parts, commercial delivery timeframe...",
    guidanceNote: "Drone service focuses on wholesale trading enquiries and equipment supply documentation.",
  },
  "mineral-water": {
    productPlaceholder: "e.g., Natural mineral water, purified drinking water, alkaline water, sparkling water",
    quantityPlaceholder: "e.g., 2,000 (Optional)",
    unitPlaceholder: "e.g., Cartons (330ml, 500ml, 600ml, 1.5L), 5L jugs, 19L gallons, 200ml cups",
    specPlaceholder: "Specify bottle/container size, mineral content requirements, pH parameters (6.5 to 8.5), or export certification...",
    notesPlaceholder: "Destination market / port, private label requirements, distribution schedule...",
    guidanceNote: "Mineral water wholesale trading enquiries cover commercial distribution and institutional procurement.",
  },
  construction: {
    productPlaceholder: "e.g., Property development, general construction, renovation & fit-out, project management, unit sales",
    quantityPlaceholder: "e.g., Project Scope (Optional)",
    unitPlaceholder: "e.g., Metric Tonnes, Units, Lots, or Project Scope",
    specPlaceholder: "Specify project type (residential, commercial, industrial), structural requirements, or fit-out scope...",
    notesPlaceholder: "Job site or project delivery location in Malaysia/region, delivery phases, commercial terms...",
    guidanceNote: "Construction / Building Promotion service coordinates property development, building contracting, and project management enquiries.",
  },
};

const DEFAULT_PROMPT: DivisionPromptConfig = {
  productPlaceholder: "Specify product, commodity grade, or commercial service required...",
  quantityPlaceholder: "e.g., 1,000 (Optional)",
  unitPlaceholder: "e.g., Metric Tonnes, Units, Cartons, or Project Scope",
  specPlaceholder: "Outline technical specifications, standards, or quality requirements...",
  notesPlaceholder: "Delivery destination, target timeline, or commercial terms...",
  guidanceNote: "All commercial enquiries are processed under standard wholesale trade documentation.",
};

// Helper to resolve division by id or code
function resolveDivision(identifier?: string): DivisionItem | undefined {
  if (!identifier) return undefined;
  let clean = identifier.trim().toLowerCase();
  // Duplicate building-promotions aliases resolve to canonical construction service
  if (clean === "building-promotions" || clean === "building_promotions" || clean === "eb-div-04") {
    clean = "construction";
  }
  // Drone alias mappings resolve to canonical agricultural-drones ID
  if (clean === "drone-solutions" || clean === "drone_solutions" || clean === "drones" || clean === "robotics" || clean === "eb-div-10") {
    clean = "agricultural-drones";
  }
  return businessDivisions.find(
    (d) => d.id.toLowerCase() === clean || d.code.toLowerCase() === clean
  );
}

function getInitialDivisionState(initialDivisionId?: string): { divisionId: string; stage: number } {
  // 1. Check prop
  if (initialDivisionId) {
    const match = resolveDivision(initialDivisionId);
    if (match) return { divisionId: match.id, stage: 2 };
  }

  // 2. Check window location query or hash if in browser
  if (typeof window !== "undefined") {
    try {
      const searchParams = new URLSearchParams(window.location.search);
      const queryDiv = searchParams.get("division") || searchParams.get("div");
      if (queryDiv) {
        const match = resolveDivision(queryDiv);
        if (match) return { divisionId: match.id, stage: 2 };
      }

      if (window.location.hash) {
        const hashStr = window.location.hash;
        const qIndex = hashStr.indexOf("?");
        if (qIndex !== -1) {
          const hashParams = new URLSearchParams(hashStr.substring(qIndex + 1));
          const hashDiv = hashParams.get("division") || hashParams.get("div");
          if (hashDiv) {
            const match = resolveDivision(hashDiv);
            if (match) return { divisionId: match.id, stage: 2 };
          }
        }
      }
    } catch {
      // Fallback gracefully
    }
  }

  return { divisionId: "", stage: 1 };
}

export function TradeEnquiryForm({
  initialDivisionId,
  lockDivision = false,
  onStateChange,
  onSuccess,
}: TradeEnquiryFormProps) {
  const formUid = useId();
  const stageHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const fallbackTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const isUserStageTransition = useRef<boolean>(false);

  const initialSetup = useRef<boolean>(false);
  const [initialResolved] = useState(() => getInitialDivisionState(initialDivisionId));

  // Four Stages: 1 = Division, 2 = Contact, 3 = Requirements, 4 = Review & Dispatch
  const [currentStage, setCurrentStage] = useState<number>(initialResolved.stage);
  const [highestVisitedStage, setHighestVisitedStage] = useState<number>(initialResolved.stage);

  const transitionToStage = useCallback((targetStage: number) => {
    isUserStageTransition.current = true;
    setCurrentStage(targetStage);
    setHighestVisitedStage((prev) => Math.max(prev, targetStage));
  }, []);

  const [formData, setFormData] = useState<FormData>({
    divisionId: initialResolved.divisionId,
    fullName: "",
    companyName: "",
    businessEmail: "",
    contactNumber: "",
    country: "",
    productFocus: "",
    quantity: "",
    unitOfMeasurement: "",
    specifications: "",
    additionalNotes: "",
  });

  const [touched, setTouched] = useState<Partial<Record<keyof FormData, boolean>>>({
    divisionId: false,
    fullName: false,
    companyName: false,
    businessEmail: false,
    contactNumber: false,
    country: false,
    productFocus: false,
    quantity: false,
    unitOfMeasurement: false,
    specifications: false,
    additionalNotes: false,
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [copied, setCopied] = useState<boolean>(false);
  const [showClipboardFallback, setShowClipboardFallback] = useState<boolean>(false);
  const [draftOpenedNotice, setDraftOpenedNotice] = useState<boolean>(false);

  const { isOnline } = useNetworkStatus();
  const { toast } = useToast();

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitSuccess, setSubmitSuccess] = useState<{ referenceNumber: string; message: string } | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const submissionIdempotencyRef = useRef<{ payloadSignature: string; key: string } | null>(null);

  const handleFocusField = useCallback((field: string) => {
    const el = document.getElementById(`${formUid}-${field}`);
    if (el) {
      el.focus();
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [formUid]);

  // Check URL on mount if rendered on client after SSR
  useEffect(() => {
    if (initialSetup.current) return;
    initialSetup.current = true;

    // In case SSR didn't have window.location
    if (!formData.divisionId && typeof window !== "undefined") {
      const detected = getInitialDivisionState(initialDivisionId);
      if (detected.divisionId) {
        // Schedule in next tick to avoid synchronous effect cascade
        setTimeout(() => {
          setFormData((prev) => ({ ...prev, divisionId: detected.divisionId }));
          setCurrentStage(detected.stage);
          setHighestVisitedStage((prev) => Math.max(prev, detected.stage));
        }, 0);
      }
    }
  }, [formData.divisionId, initialDivisionId]);

  // Listen to hash changes for in-page navigation to #inquiry?division=...
  useEffect(() => {
    const handleHashChange = (isUserEvent = false) => {
      if (typeof window === "undefined" || !window.location.hash) return;
      const hashStr = window.location.hash;
      const qIndex = hashStr.indexOf("?");
      if (qIndex !== -1) {
        const hashParams = new URLSearchParams(hashStr.substring(qIndex + 1));
        const hashDiv = hashParams.get("division") || hashParams.get("div");
        if (hashDiv) {
          const match = resolveDivision(hashDiv);
          if (match) {
            setFormData((prev) => ({ ...prev, divisionId: match.id }));
            if (isUserEvent) {
              isUserStageTransition.current = true;
            }
            setCurrentStage(2);
            setHighestVisitedStage((prev) => Math.max(prev, 2));
            if (isUserEvent) {
              const inqEl = document.getElementById("inquiry");
              if (inqEl) {
                inqEl.scrollIntoView({ behavior: "smooth" });
              }
            }
          }
        }
      }
    };

    const onHashChange = () => handleHashChange(true);
    window.addEventListener("hashchange", onHashChange);
    // On initial mount: parse state if needed, but NEVER force scroll or focus
    handleHashChange(false);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // Sync state up to parent for RFQ Summary
  const selectedDivision = businessDivisions.find((d) => d.id === formData.divisionId);

  useEffect(() => {
    onStateChange?.({
      formData,
      currentStage,
      selectedDivision,
    });
  }, [formData, currentStage, selectedDivision, onStateChange]);

  // Focus management: move focus to stage heading only upon genuine user-initiated stage transition
  useEffect(() => {
    if (isUserStageTransition.current) {
      isUserStageTransition.current = false;
      if (stageHeadingRef.current) {
        stageHeadingRef.current.focus({ preventScroll: true });
      }
    }
  }, [currentStage]);

  // Single field validation
  const validateField = (field: keyof FormData, value: string): string | undefined => {
    switch (field) {
      case "divisionId":
        if (!value.trim()) return "Please select a commercial trading division.";
        if (!businessDivisions.some((d) => d.id === value.trim())) {
          return "Invalid commercial division identifier.";
        }
        return undefined;
      case "fullName":
        if (!value.trim()) return "Contact person full name is required.";
        if (value.trim().length < 2) return "Contact name must be at least 2 characters.";
        return undefined;
      case "companyName":
        if (!value.trim()) return "Registered company or entity name is required.";
        if (value.trim().length < 2) return "Company name must be at least 2 characters.";
        return undefined;
      case "businessEmail":
        if (!value.trim()) return "Corporate business email address is required.";
        if (!EMAIL_REGEX.test(value.trim())) return "Please enter a valid business email address.";
        return undefined;
      case "country":
        if (!value.trim()) return "Country of corporate operation is required.";
        if (value.trim().length < 2) return "Please enter a valid country name.";
        return undefined;
      case "contactNumber":
        if (value.trim() && value.trim().length < 6) {
          return "Phone number must be at least 6 characters if provided.";
        }
        if (value.trim().length > 50) {
          return "Phone number must be 50 characters or fewer.";
        }
        return undefined;
      case "productFocus":
        if (!value.trim()) return "Please specify the commodity, product or focus area.";
        if (value.trim().length < 3) return "Product focus must be at least 3 characters.";
        return undefined;
      default:
        return undefined;
    }
  };

  // Stage-specific validation
  const validateStage = (stage: number): boolean => {
    const newErrors: FormErrors = {};
    let isValid = true;

    if (stage === 1) {
      const err = validateField("divisionId", formData.divisionId);
      newErrors.divisionId = err;
      if (err) {
        isValid = false;
      }
      setTouched((prev) => ({ ...prev, divisionId: true }));
    } else if (stage === 2) {
      const stage2Fields: (keyof FormErrors)[] = [
        "fullName",
        "companyName",
        "businessEmail",
        "contactNumber",
        "country",
      ];
      const touchedUpdate: Partial<Record<keyof FormData, boolean>> = {};
      stage2Fields.forEach((field) => {
        touchedUpdate[field as keyof FormData] = true;
        const val = (formData[field as keyof FormData] || "") as string;
        const err = validateField(field as keyof FormData, val);
        newErrors[field] = err;
        if (err) {
          isValid = false;
        }
      });
      setTouched((prev) => ({ ...prev, ...touchedUpdate }));
    } else if (stage === 3) {
      const err = validateField("productFocus", formData.productFocus);
      newErrors.productFocus = err;
      if (err) {
        isValid = false;
      }
      setTouched((prev) => ({ ...prev, productFocus: true }));
    }

    setErrors((prev) => ({ ...prev, ...newErrors }));
    return isValid;
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    const field = name as keyof FormData;
    setFormData((prev) => ({ ...prev, [field]: value }));

    if (touched[field] || errors[field]) {
      const err = validateField(field, value);
      setErrors((prev) => ({ ...prev, [field]: err }));
    }
  };

  const handleBlur = (
    e: React.FocusEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    const field = name as keyof FormData;
    setTouched((prev) => ({ ...prev, [field]: true }));
    const err = validateField(field, value);
    setErrors((prev) => ({ ...prev, [field]: err }));
  };

  const handleDivisionSelect = (divisionId: string) => {
    setFormData((prev) => ({ ...prev, divisionId }));
    setErrors((prev) => ({ ...prev, divisionId: undefined }));
  };

  // Advance to next stage with validation gating
  const handleNext = () => {
    if (validateStage(currentStage)) {
      transitionToStage(currentStage + 1);
    }
  };

  // Backward navigation preserving all data
  const handleBack = () => {
    if (currentStage > 1) {
      isUserStageTransition.current = true;
      setCurrentStage((prev) => prev - 1);
    }
  };

  // Direct stepper navigation (only to visited or valid stages)
  const handleStepClick = (targetStage: number) => {
    if (targetStage === currentStage) return;
    if (targetStage < currentStage) {
      transitionToStage(targetStage);
    } else {
      // Validate all intermediate stages before jumping ahead
      let canAdvance = true;
      for (let s = currentStage; s < targetStage; s++) {
        if (!validateStage(s)) {
          canAdvance = false;
          break;
        }
      }
      if (canAdvance) {
        transitionToStage(targetStage);
      }
    }
  };

  // Format clean RFQ Summary Body
  const activePrompt = (selectedDivision && DIVISION_PROMPTS[selectedDivision.id]) || DEFAULT_PROMPT;
  const divisionDisplay = selectedDivision
    ? selectedDivision.name
    : "General Wholesale Procurement";

  const rfqSummaryBody = [
    `EDEN BOUNTY Sdn. Bhd. — OFFICIAL B2B RFQ DRAFT`,
    `==================================================`,
    `COMMERCIAL DIVISION:  ${divisionDisplay}`,
    ``,
    `COMPANY & CONTACT INFORMATION:`,
    `--------------------------------------------------`,
    `Company Name:         ${formData.companyName || "Not specified"}`,
    `Country of Domicile:  ${formData.country || "Not specified"}`,
    `Contact Person:       ${formData.fullName || "Not specified"}`,
    `Business Email:       ${formData.businessEmail || "Not specified"}`,
    `Contact Phone:        ${formData.contactNumber || "Not specified"}`,
    ``,
    `COMMERCIAL REQUIREMENTS:`,
    `--------------------------------------------------`,
    `Product / Focus Area: ${formData.productFocus || "Not specified"}`,
    formData.quantity ? `Estimated Quantity:   ${formData.quantity}` : null,
    formData.unitOfMeasurement ? `Unit of Measurement:  ${formData.unitOfMeasurement}` : null,
    formData.specifications ? `Technical Specs:      ${formData.specifications}` : null,
    formData.additionalNotes ? `Commercial Remarks:   ${formData.additionalNotes}` : null,
    ``,
    `==================================================`,
    `TRANSMISSION & PRIVACY NOTICE:`,
    `Compiled locally via EDEN BOUNTY Corporate Portal (https://edenbounty.org).`,
    `Direct dispatch to official business email: ${siteConfig.contact.email}`,
    `Operating Location: Shah Alam, Selangor, Malaysia`,
  ]
    .filter((line) => line !== null)
    .join("\n");

  const emailSubject = `B2B RFQ Inquiry: ${
    selectedDivision?.name || "Wholesale Procurement"
  } — ${formData.companyName || "Trade Partner"}`;

  // Mailto with length safeguard: URL length limits in browsers (~2000 chars)
  const encodedSubject = encodeURIComponent(emailSubject);
  const encodedBody = encodeURIComponent(rfqSummaryBody);

  // Construct safe mailto URL
  let mailtoUrl = `mailto:${siteConfig.contact.email}?subject=${encodedSubject}&body=${encodedBody}`;
  if (mailtoUrl.length > 2000) {
    // Graceful truncation for mailto body while preserving full text for clipboard
    const truncatedBody = encodeURIComponent(
      rfqSummaryBody.slice(0, 1200) +
        "\n\n[... Summary condensed for email client URL limits. Full specifications available in clipboard ...]"
    );
    mailtoUrl = `mailto:${siteConfig.contact.email}?subject=${encodedSubject}&body=${truncatedBody}`;
  }

  const handleOpenEmail = () => {
    setDraftOpenedNotice(true);
    if (typeof window !== "undefined") {
      const link = document.createElement("a");
      link.href = mailtoUrl;
      link.target = "_self";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const handleCopy = async () => {
    let success = false;
    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(rfqSummaryBody);
        success = true;
        setCopied(true);
        setShowClipboardFallback(false);
        setTimeout(() => setCopied(false), 3000);
      } catch {
        success = false;
      }
    }
    if (!success) {
      setShowClipboardFallback(true);
      setTimeout(() => {
        fallbackTextareaRef.current?.focus();
        fallbackTextareaRef.current?.select();
      }, 50);
    }
  };

  const handleReset = () => {
    setFormData({
      divisionId: "",
      fullName: "",
      companyName: "",
      businessEmail: "",
      contactNumber: "",
      country: "",
      productFocus: "",
      quantity: "",
      unitOfMeasurement: "",
      specifications: "",
      additionalNotes: "",
    });
    setTouched({
      divisionId: false,
      fullName: false,
      companyName: false,
      businessEmail: false,
      contactNumber: false,
      country: false,
      productFocus: false,
      quantity: false,
      unitOfMeasurement: false,
      specifications: false,
      additionalNotes: false,
    });
    setErrors({});
    setSubmitSuccess(null);
    setSubmitError(null);
    submissionIdempotencyRef.current = null;
    transitionToStage(1);
    setDraftOpenedNotice(false);
    setShowClipboardFallback(false);
  };

  const handleSubmitOnline = async () => {
    if (!validateStage(1) || !validateStage(2) || !validateStage(3)) {
      toast.error("Please complete all required fields before submitting.");
      return;
    }
    if (!isOnline) {
      toast.warning("Network connection required for online submission. Please check connectivity or use the email draft option.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const payload = {
        division_id: formData.divisionId,
        full_name: formData.fullName.trim(),
        company_name: formData.companyName.trim(),
        business_email: formData.businessEmail.trim(),
        contact_number: formData.contactNumber.trim() || undefined,
        country: formData.country.trim(),
        product_focus: formData.productFocus.trim(),
        quantity: formData.quantity.trim() || undefined,
        unit_of_measurement: formData.unitOfMeasurement.trim() || undefined,
        specifications: formData.specifications.trim() || undefined,
        additional_notes: formData.additionalNotes.trim() || undefined,
        website_url_hp: "",
      };

      // Keep the same key for retries of this exact payload. If the user edits
      // the enquiry after a failed attempt, the changed request gets a new key.
      const payloadSignature = JSON.stringify(payload);
      if (submissionIdempotencyRef.current?.payloadSignature !== payloadSignature) {
        submissionIdempotencyRef.current = {
          payloadSignature,
          key: createIdempotencyKey(),
        };
      }
      const idempotencyKey = submissionIdempotencyRef.current.key;

      const res = await fetch("/api/v1/public/rfq/enquire", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        let msg = `Enquiry submission failed (HTTP ${res.status}).`;
        try {
          const errData = await res.json();
          if (typeof errData.detail === "string") {
            msg = errData.detail;
          } else if (Array.isArray(errData.detail) && errData.detail.length > 0) {
            msg = errData.detail[0]?.msg || msg;
          } else if (errData.message) {
            msg = errData.message;
          }
        } catch {
          // fallback
        }
        throw new Error(msg);
      }

      const resJson = await res.json();
      const refNum = resJson.data?.reference_number || "EB-RFQ-PENDING";
      const confMsg = resJson.data?.message || "Trade enquiry registered successfully in central repository.";

      setSubmitSuccess({ referenceNumber: refNum, message: confMsg });
      submissionIdempotencyRef.current = null;
      toast.success(`Trade enquiry submitted successfully. Reference: ${refNum}`);
      onSuccess?.();
    } catch (err: unknown) {
      const errDetail = err instanceof Error ? err.message : "An unexpected network error occurred while submitting your enquiry.";
      setSubmitError(errDetail);
      toast.error(errDetail);
    } finally {
      setIsSubmitting(false);
    }
  };

  const stageSteps = [
    { num: 1, label: "Services" },
    { num: 2, label: "Contact" },
    { num: 3, label: "Requirements" },
    { num: 4, label: "Review & Compile" },
  ];

  return (
    <div className="rounded-[2px] border border-line eb-glass p-3.5 sm:p-6 lg:p-7 shadow-sm space-y-6 transition-colors duration-200 w-full min-w-0 max-w-full">
      {/* 4-Node Stepper Header (2x2 on Mobile, 4-Col on Desktop) */}
      <nav
        aria-label="Enquiry Stages"
        className="border-b border-line pb-4 w-full min-w-0"
      >
        <ol className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-2.5 w-full min-w-0">
          {stageSteps.map((step) => {
            const isActive = currentStage === step.num;
            const isCompleted = currentStage > step.num;
            const isClickable = (isCompleted || step.num <= highestVisitedStage) && !(lockDivision && step.num === 1);

            return (
              <li key={step.num} className="min-w-0 w-full">
                <button
                  type="button"
                  onClick={() => isClickable && handleStepClick(step.num)}
                  disabled={!isClickable}
                  aria-current={isActive ? "step" : undefined}
                  className={`w-full min-w-0 min-h-[48px] rounded-[2px] p-2 sm:px-2 sm:py-2.5 lg:px-2.5 flex items-center justify-start sm:justify-center transition-all duration-200 cursor-pointer motion-reduce:transition-none text-left sm:text-center ${
                    isActive
                      ? "border border-brand  bg-brand-soft  text-brand  font-bold shadow-sm "
                      : isCompleted
                      ? "border border-[#A7F3D0] dark:border-[#10B981]/40 bg-[#ECFDF5] dark:bg-[#10B981]/10 text-[#059669] dark:text-[#10B981] hover:border-[#059669] dark:hover:border-[#10B981]"
                      : isClickable
                      ? "border border-line-strong  bg-panel-2  text-ink-subtle  hover:border-ink-subtle "
                      : "border border-line  bg-panel-2  text-ink-subtle  cursor-not-allowed"
                  }`}
                >
                  <div className="flex items-center gap-1.5 sm:gap-1.5 w-full min-w-0">
                    {isCompleted ? (
                      <Check className="h-3.5 w-3.5 text-[#059669] dark:text-[#10B981] shrink-0" />
                    ) : (
                      <span
                        className={`h-2 w-2 rounded-full shrink-0 ${
                          isActive
                            ? "bg-brand   "
                            : "bg-ink-subtle "
                        }`}
                      />
                    )}
                    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-0 sm:gap-1 min-w-0 flex-1">
                      <span className="font-mono text-xs font-bold leading-tight shrink-0">
                        {`0${step.num}`}
                      </span>
                      <span className="font-heading text-[11px] sm:text-xs font-semibold uppercase tracking-normal sm:tracking-tight lg:tracking-normal leading-tight min-w-0 break-words block">
                        {step.label}
                      </span>
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      {/* Main Active Stage Container */}
      <div className="space-y-6 w-full min-w-0 max-w-full">
        {/* Stage 01: Commercial Division Selection */}
        {currentStage === 1 && (
          <div className="space-y-5 animate-in fade-in duration-200 motion-reduce:animate-none w-full min-w-0 max-w-full">
            <div className="space-y-1 w-full min-w-0">
              <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                <span className="font-mono text-[11px] text-brand uppercase tracking-widest font-semibold">
                  Stage 01 of 04
                </span>
                <span className="text-line-strong">•</span>
                <span className="font-mono text-[11px] text-ink-subtle uppercase">
                  Commercial Scoping
                </span>
              </div>
              <h3
                ref={stageHeadingRef}
                tabIndex={-1}
                className="font-heading text-base sm:text-xl font-bold text-ink outline-none break-words leading-snug"
              >
                Select Commercial Trading Service
              </h3>
              <p className="font-body text-xs sm:text-sm text-ink-muted break-words leading-relaxed">
                Choose from EDEN BOUNTY Sdn. Bhd.&apos;s commercial services to initiate your Request for Quotation.
              </p>
            </div>

            {errors.divisionId && (
              <div
                role="alert"
                className="p-3 rounded-[2px] border border-[#FECACA] dark:border-[#EF4444]/40 bg-[#FEF2F2] dark:bg-[#EF4444]/10 text-xs text-[#DC2626] dark:text-[#F87171] font-mono flex items-center gap-2 w-full min-w-0"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span className="break-words">{errors.divisionId}</span>
              </div>
            )}

            {/* Division Grid (active divisions only) */}
            <div
              role="radiogroup"
              aria-label="Commercial Services"
              className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3 w-full min-w-0"
            >
              {businessDivisions.map((div) => {
                const isSelected = formData.divisionId === div.id;
                const IconComponent = DIVISION_ICONS[div.id] || Layers;

                return (
                  <button
                    type="button"
                    key={div.id}
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => handleDivisionSelect(div.id)}
                    className={`w-full min-h-[56px] text-left p-2.5 sm:p-3 rounded-[2px] border transition-all duration-150 cursor-pointer flex items-center justify-between motion-reduce:transition-none min-w-0 max-w-full ${
                      isSelected
                        ? "border-brand  bg-brand-soft  shadow-sm text-ink  ring-1 ring-brand "
                        : "border-line  bg-panel  text-ink-muted  hover:border-brand/50  hover:bg-panel-2 "
                    }`}
                  >
                    <div className="flex items-center gap-2.5 sm:gap-3 min-w-0 flex-1">
                      <div
                        className={`h-9 w-9 rounded-[2px] border flex items-center justify-center shrink-0 transition-colors ${
                          isSelected
                            ? "border-brand  bg-brand-soft  text-brand "
                            : "border-line  bg-panel-2  text-ink-subtle "
                        }`}
                      >
                        <IconComponent className="h-4 w-4 shrink-0" />
                      </div>
                      <div className="space-y-0.5 min-w-0 flex-1">
                        <span className="font-heading font-semibold text-xs sm:text-sm text-ink block truncate">
                          {div.name}
                        </span>
                      </div>
                    </div>

                    <div
                      className={`h-4 w-4 rounded-full border flex items-center justify-center shrink-0 ml-2 ${
                        isSelected
                          ? "border-brand  bg-brand "
                          : "border-line-strong  bg-transparent"
                      }`}
                    >
                      {isSelected && <span className="h-1.5 w-1.5 rounded-full bg-panel" />}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Stage 01 Action Bar */}
            <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-t border-line w-full min-w-0">
              <div className="text-[11px] font-mono text-ink-subtle text-center sm:text-left min-w-0 break-words">
                {selectedDivision ? (
                  <span className="text-brand font-semibold break-words">
                    Selected: {selectedDivision.name}
                  </span>
                ) : (
                  <span>Select a service to proceed</span>
                )}
              </div>

              <button
                type="button"
                onClick={handleNext}
                disabled={!formData.divisionId}
                className={`w-full sm:w-auto min-h-[48px] inline-flex items-center justify-center gap-2 rounded-[2px] px-4 sm:px-6 py-2.5 font-heading text-[11px] sm:text-xs font-semibold uppercase tracking-wider transition-all duration-200 cursor-pointer max-w-full min-w-0 ${
                  formData.divisionId
                    ? "bg-brand  text-brand-ink hover:bg-brand-hover  shadow-sm"
                    : "bg-line  text-ink-subtle  cursor-not-allowed"
                }`}
              >
                <span className="truncate">Continue to Contact Details</span>
                <ArrowRight className="h-4 w-4 shrink-0" />
              </button>
            </div>
          </div>
        )}

        {/* Stage 02: Company & Contact Details */}
        {currentStage === 2 && (
          <div className="space-y-5 animate-in fade-in duration-200 motion-reduce:animate-none w-full min-w-0 max-w-full">
            <div className="space-y-1 w-full min-w-0">
              <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                <span className="font-mono text-[11px] text-brand uppercase tracking-widest font-semibold">
                  Stage 02 of 04
                </span>
                <span className="text-line-strong">•</span>
                <span className="font-mono text-[11px] text-ink-subtle uppercase">
                  {selectedDivision ? selectedDivision.name : "Commercial Service"}
                </span>
              </div>
              <h3
                ref={stageHeadingRef}
                tabIndex={-1}
                className="font-heading text-base sm:text-xl font-bold text-ink outline-none break-words leading-snug"
              >
                Company & Contact Information
              </h3>
              <p className="font-body text-xs sm:text-sm text-ink-muted break-words leading-relaxed">
                Enter verified business representative and registered corporate entity credentials.
              </p>
            </div>

            {/* Form Validation Error Summary */}
            <FormErrorSummary
              errors={errors}
              title="Please Correct Contact Details"
              onFieldClick={handleFocusField}
            />

            <div className="space-y-4 w-full min-w-0 max-w-full">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 w-full min-w-0">
                {/* Contact Person */}
                <div className="space-y-1.5 min-w-0">
                  <label
                    htmlFor={`${formUid}-fullName`}
                    className="flex items-center gap-1.5 font-heading text-xs font-medium text-ink-muted"
                  >
                    <User className="h-3.5 w-3.5 text-brand shrink-0" />
                    <span className="truncate">Contact Person Name *</span>
                  </label>
                  <input
                    id={`${formUid}-fullName`}
                    name="fullName"
                    type="text"
                    autoComplete="name"
                    value={formData.fullName}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    aria-required="true"
                    aria-invalid={!!errors.fullName}
                    aria-describedby={errors.fullName ? `${formUid}-fullName-error` : undefined}
                    placeholder="e.g., Marcus Tan"
                    className={`w-full min-h-[48px] rounded-[2px] border bg-panel  px-3 sm:px-3.5 py-2 text-xs sm:text-sm text-ink  placeholder-ink-subtle  transition-colors focus-visible:outline-none focus-visible:ring-1 min-w-0 max-w-full ${
                      errors.fullName
                        ? "border-[#EF4444] focus-visible:ring-[#EF4444]"
                        : "border-line-strong  focus-visible:border-brand  focus-visible:ring-brand "
                    }`}
                  />
                  {errors.fullName && (
                    <p
                      id={`${formUid}-fullName-error`}
                      role="alert"
                      className="flex items-center gap-1 text-[11px] text-[#DC2626] dark:text-[#F87171] font-mono pt-0.5 break-words"
                    >
                      <AlertCircle className="h-3 w-3 shrink-0" />
                      <span>{errors.fullName}</span>
                    </p>
                  )}
                </div>

                {/* Company Name */}
                <div className="space-y-1.5 min-w-0">
                  <label
                    htmlFor={`${formUid}-companyName`}
                    className="flex items-center gap-1.5 font-heading text-xs font-medium text-ink-muted"
                  >
                    <Building2 className="h-3.5 w-3.5 text-brand shrink-0" />
                    <span className="truncate">Registered Company / Entity Name *</span>
                  </label>
                  <input
                    id={`${formUid}-companyName`}
                    name="companyName"
                    type="text"
                    autoComplete="organization"
                    value={formData.companyName}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    aria-required="true"
                    aria-invalid={!!errors.companyName}
                    aria-describedby={errors.companyName ? `${formUid}-companyName-error` : undefined}
                    placeholder="e.g., Apex Commercial Holdings Ltd."
                    className={`w-full min-h-[48px] rounded-[2px] border bg-panel  px-3 sm:px-3.5 py-2 text-xs sm:text-sm text-ink  placeholder-ink-subtle  transition-colors focus-visible:outline-none focus-visible:ring-1 min-w-0 max-w-full ${
                      errors.companyName
                        ? "border-[#EF4444] focus-visible:ring-[#EF4444]"
                        : "border-line-strong  focus-visible:border-brand  focus-visible:ring-brand "
                    }`}
                  />
                  {errors.companyName && (
                    <p
                      id={`${formUid}-companyName-error`}
                      role="alert"
                      className="flex items-center gap-1 text-[11px] text-[#DC2626] dark:text-[#F87171] font-mono pt-0.5 break-words"
                    >
                      <AlertCircle className="h-3 w-3 shrink-0" />
                      <span>{errors.companyName}</span>
                    </p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 w-full min-w-0">
                {/* Business Email */}
                <div className="space-y-1.5 min-w-0">
                  <label
                    htmlFor={`${formUid}-businessEmail`}
                    className="flex items-center gap-1.5 font-heading text-xs font-medium text-ink-muted"
                  >
                    <Mail className="h-3.5 w-3.5 text-brand shrink-0" />
                    <span className="truncate">Business Email Address *</span>
                  </label>
                  <input
                    id={`${formUid}-businessEmail`}
                    name="businessEmail"
                    type="email"
                    autoComplete="email"
                    value={formData.businessEmail}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    aria-required="true"
                    aria-invalid={!!errors.businessEmail}
                    aria-describedby={errors.businessEmail ? `${formUid}-businessEmail-error` : undefined}
                    placeholder="e.g., m.tan@apexholdings.sg"
                    className={`w-full min-h-[48px] rounded-[2px] border bg-panel  px-3 sm:px-3.5 py-2 text-xs sm:text-sm text-ink  placeholder-ink-subtle  transition-colors focus-visible:outline-none focus-visible:ring-1 min-w-0 max-w-full ${
                      errors.businessEmail
                        ? "border-[#EF4444] focus-visible:ring-[#EF4444]"
                        : "border-line-strong  focus-visible:border-brand  focus-visible:ring-brand "
                    }`}
                  />
                  {errors.businessEmail && (
                    <p
                      id={`${formUid}-businessEmail-error`}
                      role="alert"
                      className="flex items-center gap-1 text-[11px] text-[#DC2626] dark:text-[#F87171] font-mono pt-0.5 break-words"
                    >
                      <AlertCircle className="h-3 w-3 shrink-0" />
                      <span>{errors.businessEmail}</span>
                    </p>
                  )}
                </div>

                {/* Country of Operation (Standard Input) */}
                <div className="space-y-1.5 min-w-0">
                  <label
                    htmlFor={`${formUid}-country`}
                    className="flex items-center gap-1.5 font-heading text-xs font-medium text-ink-muted"
                  >
                    <Globe className="h-3.5 w-3.5 text-brand shrink-0" />
                    <span className="truncate">Country of Domicile / Operation *</span>
                  </label>
                  <input
                    id={`${formUid}-country`}
                    name="country"
                    type="text"
                    autoComplete="country-name"
                    value={formData.country}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    aria-required="true"
                    aria-invalid={!!errors.country}
                    aria-describedby={errors.country ? `${formUid}-country-error` : undefined}
                    placeholder="e.g., Singapore, Malaysia, United Arab Emirates"
                    className={`w-full min-h-[48px] rounded-[2px] border bg-panel  px-3 sm:px-3.5 py-2 text-xs sm:text-sm text-ink  placeholder-ink-subtle  transition-colors focus-visible:outline-none focus-visible:ring-1 min-w-0 max-w-full ${
                      errors.country
                        ? "border-[#EF4444] focus-visible:ring-[#EF4444]"
                        : "border-line-strong  focus-visible:border-brand  focus-visible:ring-brand "
                    }`}
                  />
                  {errors.country && (
                    <p
                      id={`${formUid}-country-error`}
                      role="alert"
                      className="flex items-center gap-1 text-[11px] text-[#DC2626] dark:text-[#F87171] font-mono pt-0.5 break-words"
                    >
                      <AlertCircle className="h-3 w-3 shrink-0" />
                      <span>{errors.country}</span>
                    </p>
                  )}
                </div>
              </div>

              {/* Contact Phone (Optional) */}
              <div className="space-y-1.5 min-w-0">
                <label
                  htmlFor={`${formUid}-contactNumber`}
                  className="flex items-center justify-between font-heading text-xs font-medium text-ink-muted gap-2"
                >
                  <span className="flex items-center gap-1.5 min-w-0">
                    <Phone className="h-3.5 w-3.5 text-brand shrink-0" />
                    <span className="truncate">Business Telephone / Mobile</span>
                  </span>
                  <span className="font-mono text-[10px] text-ink-subtle uppercase shrink-0">Optional</span>
                </label>
                <input
                  id={`${formUid}-contactNumber`}
                  name="contactNumber"
                  type="tel"
                  autoComplete="tel"
                  maxLength={50}
                  value={formData.contactNumber}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  aria-invalid={!!errors.contactNumber}
                  aria-describedby={errors.contactNumber ? `${formUid}-contactNumber-error` : undefined}
                  placeholder="e.g., +65 6789 0123"
                  className={`w-full min-h-[48px] rounded-[2px] border bg-panel  px-3 sm:px-3.5 py-2 text-xs sm:text-sm text-ink  placeholder-ink-subtle  transition-colors focus-visible:outline-none focus-visible:ring-1 min-w-0 max-w-full ${
                    errors.contactNumber
                      ? "border-[#EF4444] focus-visible:ring-[#EF4444]"
                      : "border-line-strong  focus-visible:border-brand  focus-visible:ring-brand "
                  }`}
                />
                {errors.contactNumber && (
                  <p
                    id={`${formUid}-contactNumber-error`}
                    role="alert"
                    className="flex items-center gap-1 text-[11px] text-[#DC2626] dark:text-[#F87171] font-mono pt-0.5 break-words"
                  >
                    <AlertCircle className="h-3 w-3 shrink-0" />
                    <span>{errors.contactNumber}</span>
                  </p>
                )}
              </div>
            </div>

            {/* Stage 02 Action Bar */}
            <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-t border-line w-full min-w-0">
              {lockDivision ? (
                <div className="flex items-center gap-2 text-xs font-mono text-ink-subtle px-1 py-2">
                  <span className="h-2 w-2 rounded-full bg-brand" />
                  <span>Service: {selectedDivision?.name || "Pre-selected"}</span>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={handleBack}
                  className="w-full sm:w-auto min-h-[48px] inline-flex items-center justify-center gap-2 rounded-[2px] border border-line-strong bg-panel px-4 sm:px-5 py-2.5 font-heading text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-ink-muted hover:text-ink hover:border-ink-subtle transition-colors cursor-pointer max-w-full min-w-0"
                >
                  <ArrowLeft className="h-4 w-4 shrink-0" />
                  <span>Back to Services</span>
                </button>
              )}

              <button
                type="button"
                onClick={handleNext}
                className="w-full sm:w-auto min-h-[48px] inline-flex items-center justify-center gap-2 rounded-[2px] bg-brand px-4 sm:px-6 py-2.5 font-heading text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-brand-ink hover:bg-brand-hover transition-all duration-200 cursor-pointer shadow-sm max-w-full min-w-0"
              >
                <span className="truncate">Continue to Requirements</span>
                <ArrowRight className="h-4 w-4 shrink-0" />
              </button>
            </div>
          </div>
        )}

        {/* Stage 03: Commercial Requirements & Prompts */}
        {currentStage === 3 && (
          <div className="space-y-5 animate-in fade-in duration-200 motion-reduce:animate-none w-full min-w-0 max-w-full">
            <div className="space-y-1 w-full min-w-0">
              <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                <span className="font-mono text-[11px] text-brand uppercase tracking-widest font-semibold">
                  Stage 03 of 04
                </span>
                <span className="text-line-strong">•</span>
                <span className="font-mono text-[11px] text-ink-subtle uppercase">
                  {selectedDivision ? selectedDivision.name : "Requirements"}
                </span>
              </div>
              <h3
                ref={stageHeadingRef}
                tabIndex={-1}
                className="font-heading text-base sm:text-xl font-bold text-ink outline-none break-words leading-snug"
              >
                Commercial Requirements & Specifications
              </h3>
              <p className="font-body text-xs sm:text-sm text-ink-muted break-words leading-relaxed">
                Specify target commodities, optional volumes, and commercial terms. Prompts adapt to your chosen service.
              </p>
            </div>

            {/* Form Validation Error Summary */}
            <FormErrorSummary
              errors={errors}
              title="Please Correct Scope Details"
              onFieldClick={handleFocusField}
            />

            {/* Service Guidance Notice */}
            <div className="rounded-[2px] border border-brand/40 bg-brand-soft p-3 sm:p-3.5 text-xs text-brand-hover flex items-start gap-2.5 w-full min-w-0 max-w-full">
              <HelpCircle className="h-4 w-4 text-brand shrink-0 mt-0.5" />
              <div className="space-y-0.5 min-w-0 flex-1">
                <span className="font-mono text-[10px] uppercase tracking-wider text-brand block font-semibold truncate">
                  Service Guidance: {selectedDivision?.name || "Wholesale Service"}
                </span>
                <p className="font-body text-[11px] text-ink-muted leading-relaxed break-words">
                  {activePrompt.guidanceNote}
                </p>
              </div>
            </div>

            <div className="space-y-4 w-full min-w-0 max-w-full">
              {/* Product / Scope Focus */}
              <div className="space-y-1.5 min-w-0">
                <label
                  htmlFor={`${formUid}-productFocus`}
                  className="flex items-center gap-1.5 font-heading text-xs font-medium text-ink-muted"
                >
                  <FileText className="h-3.5 w-3.5 text-brand shrink-0" />
                  <span className="truncate">Product, Commodity or Scope Focus *</span>
                </label>
                <input
                  id={`${formUid}-productFocus`}
                  name="productFocus"
                  type="text"
                  value={formData.productFocus}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  aria-required="true"
                  aria-invalid={!!errors.productFocus}
                  aria-describedby={errors.productFocus ? `${formUid}-productFocus-error` : undefined}
                  placeholder={activePrompt.productPlaceholder}
                  className={`w-full min-h-[48px] rounded-[2px] border bg-panel  px-3 sm:px-3.5 py-2 text-xs sm:text-sm text-ink  placeholder-ink-subtle  transition-colors focus-visible:outline-none focus-visible:ring-1 min-w-0 max-w-full ${
                    errors.productFocus
                      ? "border-[#EF4444] focus-visible:ring-[#EF4444]"
                      : "border-line-strong  focus-visible:border-brand  focus-visible:ring-brand "
                  }`}
                />
                {errors.productFocus && (
                  <p
                    id={`${formUid}-productFocus-error`}
                    role="alert"
                    className="flex items-center gap-1 text-[11px] text-[#DC2626] dark:text-[#F87171] font-mono pt-0.5 break-words"
                  >
                    <AlertCircle className="h-3 w-3 shrink-0" />
                    <span>{errors.productFocus}</span>
                  </p>
                )}
              </div>

              {/* Quantity (Optional) & Unit of Measurement (Flexible Text) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 w-full min-w-0">
                <div className="space-y-1.5 min-w-0">
                  <label
                    htmlFor={`${formUid}-quantity`}
                    className="flex items-center justify-between font-heading text-xs font-medium text-ink-muted gap-2"
                  >
                    <span className="truncate">Estimated Quantity / Volume</span>
                    <span className="font-mono text-[10px] text-ink-subtle uppercase shrink-0">Optional</span>
                  </label>
                  <input
                    id={`${formUid}-quantity`}
                    name="quantity"
                    type="text"
                    value={formData.quantity}
                    onChange={handleChange}
                    placeholder={activePrompt.quantityPlaceholder}
                    className="w-full min-h-[48px] rounded-[2px] border border-line-strong bg-panel px-3 sm:px-3.5 py-2 text-xs sm:text-sm text-ink placeholder-ink-subtle transition-colors focus-visible:outline-none focus-visible:border-brand focus-visible:ring-1 focus-visible:ring-brand min-w-0 max-w-full"
                  />
                </div>

                <div className="space-y-1.5 min-w-0">
                  <label
                    htmlFor={`${formUid}-unitOfMeasurement`}
                    className="flex items-center justify-between font-heading text-xs font-medium text-ink-muted gap-2"
                  >
                    <span className="truncate">Unit of Measurement (Flexible)</span>
                    <span className="font-mono text-[10px] text-ink-subtle uppercase shrink-0">Optional</span>
                  </label>
                  <input
                    id={`${formUid}-unitOfMeasurement`}
                    name="unitOfMeasurement"
                    type="text"
                    value={formData.unitOfMeasurement}
                    onChange={handleChange}
                    placeholder={activePrompt.unitPlaceholder}
                    className="w-full min-h-[48px] rounded-[2px] border border-line-strong bg-panel px-3 sm:px-3.5 py-2 text-xs sm:text-sm text-ink placeholder-ink-subtle transition-colors focus-visible:outline-none focus-visible:border-brand focus-visible:ring-1 focus-visible:ring-brand min-w-0 max-w-full"
                  />
                </div>
              </div>

              {/* Technical Specifications (Optional) */}
              <div className="space-y-1.5 min-w-0">
                <label
                  htmlFor={`${formUid}-specifications`}
                  className="flex items-center justify-between font-heading text-xs font-medium text-ink-muted gap-2"
                >
                  <span className="truncate">Technical Specifications & Standards</span>
                  <span className="font-mono text-[10px] text-ink-subtle uppercase shrink-0">Optional</span>
                </label>
                <textarea
                  id={`${formUid}-specifications`}
                  name="specifications"
                  rows={3}
                  value={formData.specifications}
                  onChange={handleChange}
                  placeholder={activePrompt.specPlaceholder}
                  className="w-full rounded-[2px] border border-line-strong bg-panel p-3 text-xs sm:text-sm text-ink placeholder-ink-subtle transition-colors focus-visible:outline-none focus-visible:border-brand focus-visible:ring-1 focus-visible:ring-brand min-w-0 max-w-full"
                />
              </div>

              {/* Commercial Remarks & Timeline (Optional) */}
              <div className="space-y-1.5 min-w-0">
                <label
                  htmlFor={`${formUid}-additionalNotes`}
                  className="flex items-center justify-between font-heading text-xs font-medium text-ink-muted gap-2"
                >
                  <span className="truncate">Commercial Remarks, Delivery Terms & Timeline</span>
                  <span className="font-mono text-[10px] text-ink-subtle uppercase shrink-0">Optional</span>
                </label>
                <textarea
                  id={`${formUid}-additionalNotes`}
                  name="additionalNotes"
                  rows={3}
                  value={formData.additionalNotes}
                  onChange={handleChange}
                  placeholder={activePrompt.notesPlaceholder}
                  className="w-full rounded-[2px] border border-line-strong bg-panel p-3 text-xs sm:text-sm text-ink placeholder-ink-subtle transition-colors focus-visible:outline-none focus-visible:border-brand focus-visible:ring-1 focus-visible:ring-brand min-w-0 max-w-full"
                />
              </div>
            </div>

            {/* Stage 03 Action Bar */}
            <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-t border-line w-full min-w-0">
              <button
                type="button"
                onClick={handleBack}
                className="w-full sm:w-auto min-h-[48px] inline-flex items-center justify-center gap-2 rounded-[2px] border border-line-strong bg-panel px-4 sm:px-5 py-2.5 font-heading text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-ink-muted hover:text-ink hover:border-ink-subtle transition-colors cursor-pointer max-w-full min-w-0"
              >
                <ArrowLeft className="h-4 w-4 shrink-0" />
                <span>Back to Contact</span>
              </button>

              <button
                type="button"
                onClick={handleNext}
                className="w-full sm:w-auto min-h-[48px] inline-flex items-center justify-center gap-2 rounded-[2px] bg-brand px-4 sm:px-6 py-2.5 font-heading text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-brand-ink hover:bg-brand-hover transition-all duration-200 cursor-pointer shadow-sm max-w-full min-w-0"
              >
                <span className="truncate">Review & Compile RFQ</span>
                <ArrowRight className="h-4 w-4 shrink-0" />
              </button>
            </div>
          </div>
        )}

        {/* Stage 04: Review, Dispatch & Fallback */}
        {currentStage === 4 && (
          <div className="space-y-6 animate-in fade-in duration-200 motion-reduce:animate-none w-full min-w-0 max-w-full">
            {submitSuccess ? (
              <div
                role="region"
                aria-label="Enquiry Submission Confirmation"
                className="rounded-[2px] border border-[#86EFAC] dark:border-[#059669]/40 bg-[#F0FDF4] dark:bg-[#061A0E] p-6 sm:p-8 space-y-6 text-center animate-in fade-in zoom-in-95 duration-200"
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#DCFCE7] dark:bg-[#0A2E17] border border-[#86EFAC] dark:border-[#10B981] text-[#16A34A] dark:text-[#34D399] mx-auto shadow-sm">
                  <CheckCircle2 className="h-8 w-8" />
                </div>

                <div className="space-y-2 max-w-md mx-auto">
                  <span className="inline-block px-2.5 py-0.5 rounded-[2px] bg-[#DCFCE7] dark:bg-[#0A2E17] text-[#16A34A] dark:text-[#34D399] font-mono text-[11px] font-semibold uppercase tracking-wider">
                    Commercial Request Registered
                  </span>
                  <h3 className="font-heading text-lg sm:text-xl font-bold text-ink">
                    Trade Enquiry Confirmed
                  </h3>
                  <p className="font-body text-xs sm:text-sm text-ink-muted leading-relaxed">
                    {submitSuccess.message}
                  </p>
                </div>

                {/* Reference Number Box */}
                <div className="max-w-md mx-auto p-4 rounded-[2px] border border-[#BBF7D0] dark:border-[#059669]/50 eb-glass space-y-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-ink-subtle block">
                    Assigned Commercial Reference
                  </span>
                  <div className="flex items-center justify-center gap-2">
                    <span className="font-mono text-sm sm:text-base font-bold text-brand break-all select-all">
                      {submitSuccess.referenceNumber}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(submitSuccess.referenceNumber);
                        toast.success("Reference number copied to clipboard.");
                      }}
                      className="p-1 rounded hover:bg-panel-2 text-ink-subtle transition-colors"
                      title="Copy Reference Number"
                      aria-label="Copy Reference Number"
                    >
                      <Copy className="h-4 w-4" />
                    </button>
                  </div>
                  <p className="text-[10px] font-body text-ink-subtle">
                    Please quote this reference in all future commercial correspondence.
                  </p>
                </div>

                {/* Next Steps Information */}
                <div className="max-w-md mx-auto text-left text-xs font-body text-ink-muted space-y-1 bg-white/60 p-4 rounded-[2px] border border-line">
                  <div className="font-heading font-semibold text-[11px] uppercase tracking-wider text-ink">
                    Next Operational Steps:
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                    <li>Enquiry registered and logged in the central commercial repository.</li>
                    <li>Commercial parameters cataloged under your assigned reference.</li>
                    <li>Our commercial desk will review your specifications accordingly.</li>
                  </ul>
                </div>

                {/* Buttons */}
                <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center gap-2 rounded-[2px] border border-line-strong bg-panel px-4 py-2 font-heading text-xs font-semibold uppercase tracking-wider text-ink-muted hover:border-brand hover:text-brand transition-colors cursor-pointer"
                  >
                    <Copy className="h-4 w-4" />
                    <span>Copy Full RFQ Summary</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleReset}
                    className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center gap-2 rounded-[2px] bg-brand text-brand-ink px-5 py-2 font-heading text-xs font-semibold uppercase tracking-wider hover:bg-brand-hover transition-all cursor-pointer shadow-sm"
                  >
                    <RotateCcw className="h-4 w-4" />
                    <span>Submit Another RFQ</span>
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="space-y-1 w-full min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                    <span className="font-mono text-[11px] text-brand uppercase tracking-widest font-semibold">
                      Stage 04 of 04
                    </span>
                    <span className="text-line-strong">•</span>
                    <span className="font-mono text-[11px] text-[#059669] dark:text-[#10B981] uppercase font-semibold">
                      Ready for Review
                    </span>
                  </div>
                  <h3
                    ref={stageHeadingRef}
                    tabIndex={-1}
                    className="font-heading text-base sm:text-xl font-bold text-ink outline-none break-words leading-snug"
                  >
                    Review Parameters & Transmit RFQ
                  </h3>
                  <p className="font-body text-xs sm:text-sm text-ink-muted break-words leading-relaxed">
                    Review your commercial inquiry parameters. You may edit any stage or proceed to transmit directly to the central registry.
                  </p>
                </div>

                {/* Offline Warning Notice if disconnected */}
                {!isOnline && (
                  <div
                    role="status"
                    className="rounded-[2px] border border-[#FDE68A] dark:border-[#B45309]/50 bg-[#FFFBEB] dark:bg-[#1C150A] p-3 sm:p-3.5 text-xs text-[#92400E] dark:text-[#FCD34D] flex items-center gap-2.5 w-full min-w-0 max-w-full"
                  >
                    <WifiOff className="h-4 w-4 shrink-0 text-[#D97706]" />
                    <span className="font-body leading-relaxed">
                      <strong>Working in Offline Mode:</strong> Internet connectivity is required for direct online registration. You may copy your RFQ summary or draft an email locally while offline.
                    </span>
                  </div>
                )}

                {/* Submission Error Banner */}
                {submitError && (
                  <div
                    role="alert"
                    aria-live="assertive"
                    className="rounded-[2px] border border-[#FCA5A5] dark:border-[#7F1D1D] bg-[#FEF2F2] dark:bg-[#1A0A0C] p-3.5 text-xs text-[#991B1B] dark:text-[#FCA5A5] space-y-2 w-full min-w-0 max-w-full"
                  >
                    <div className="flex items-center gap-2 font-heading font-bold uppercase tracking-wider text-[11px]">
                      <AlertCircle className="h-4 w-4 shrink-0 text-[#DC2626] dark:text-[#EF4444]" />
                      <span>Online Submission Error</span>
                    </div>
                    <p className="font-body text-[#B91C1C] dark:text-[#F87171] leading-relaxed">{submitError}</p>
                    <button
                      type="button"
                      onClick={handleSubmitOnline}
                      disabled={isSubmitting || !isOnline}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] bg-[#DC2626] dark:bg-[#EF4444] text-white font-heading text-[11px] font-semibold uppercase tracking-wider hover:bg-[#B91C1C] disabled:opacity-50 cursor-pointer shadow-sm"
                    >
                      {isSubmitting ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCcw className="h-3 w-3" />}
                      <span>Retry Submission</span>
                    </button>
                  </div>
                )}

            {/* Notification if user clicked "Open Email Application" */}
            {draftOpenedNotice && (
              <div
                role="alert"
                aria-live="polite"
                className="rounded-[2px] border border-[#A7F3D0] dark:border-[#10B981]/40 bg-[#ECFDF5] dark:bg-[#10B981]/10 p-3 sm:p-3.5 text-xs text-[#065F46] dark:text-[#A7F3D0] space-y-1 w-full min-w-0 max-w-full"
              >
                <div className="flex items-center gap-2 text-[#059669] dark:text-[#10B981] font-semibold font-heading">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span className="truncate">Email Draft Prepared in Your Email Software</span>
                </div>
                <p className="text-[11px] text-[#047857] leading-relaxed break-words">
                  Your mail application was initiated with this pre-filled RFQ draft directed to <strong className="text-brand font-mono break-all">{siteConfig.contact.email}</strong>. Opening an email draft does not automatically dispatch it; please review and press send in your email client.
                </p>
              </div>
            )}

            {/* Structured Pre-Dispatch Dossier */}
            <div className="rounded-[2px] border border-line bg-panel-2 p-3.5 sm:p-5 space-y-4 font-mono text-xs w-full min-w-0 max-w-full">
              {/* Service Section */}
              <div className="flex items-center justify-between border-b border-line pb-2 sm:pb-2.5 gap-2 min-w-0">
                <div className="min-w-0 flex-1">
                  <span className="text-ink-subtle block text-[10px] uppercase">
                    Commercial Service
                  </span>
                  <span className="font-heading text-xs sm:text-sm font-semibold text-ink break-words block">
                    {divisionDisplay}
                  </span>
                </div>
                {!lockDivision ? (
                  <button
                    type="button"
                    onClick={() => transitionToStage(1)}
                    className="inline-flex min-h-[48px] items-center gap-1 text-[11px] text-brand hover:underline cursor-pointer font-semibold shrink-0 px-2 py-1"
                  >
                    <Edit3 className="h-3.5 w-3.5 shrink-0" />
                    <span>Edit Service</span>
                  </button>
                ) : (
                  <span className="text-[10px] font-mono uppercase text-ink-subtle tracking-wider px-2 py-1">
                    Pre-selected
                  </span>
                )}
              </div>

              {/* Company & Contact Section */}
              <div className="space-y-2 border-b border-line pb-2 sm:pb-2.5 min-w-0 w-full">
                <div className="flex items-center justify-between gap-2 min-w-0">
                  <span className="text-ink-subtle text-[10px] uppercase font-semibold truncate">
                    Contact & Entity Details
                  </span>
                  <button
                    type="button"
                    onClick={() => transitionToStage(2)}
                    className="inline-flex min-h-[48px] items-center gap-1 text-[11px] text-brand hover:underline cursor-pointer font-semibold shrink-0 px-2 py-1"
                  >
                    <Edit3 className="h-3.5 w-3.5 shrink-0" />
                    <span>Edit Contact</span>
                  </button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-ink-muted min-w-0 w-full">
                  <div className="min-w-0 break-words">
                    <span className="text-ink-subtle block text-[10px]">Entity Name:</span>
                    <span className="text-ink font-medium break-words">{formData.companyName || "—"}</span>
                  </div>
                  <div className="min-w-0 break-words">
                    <span className="text-ink-subtle block text-[10px]">Representative:</span>
                    <span className="text-ink font-medium break-words">{formData.fullName || "—"}</span>
                  </div>
                  <div className="min-w-0 break-words">
                    <span className="text-ink-subtle block text-[10px]">Business Email:</span>
                    <span className="text-ink font-medium break-all">{formData.businessEmail || "—"}</span>
                  </div>
                  <div className="min-w-0 break-words">
                    <span className="text-ink-subtle block text-[10px]">Country of Domicile:</span>
                    <span className="text-ink font-medium break-words">{formData.country || "—"}</span>
                  </div>
                  {formData.contactNumber && (
                    <div className="sm:col-span-2 min-w-0 break-words">
                      <span className="text-ink-subtle block text-[10px]">Phone Number:</span>
                      <span className="text-ink font-medium break-words">{formData.contactNumber}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Requirements Section */}
              <div className="space-y-2 min-w-0 w-full">
                <div className="flex items-center justify-between gap-2 min-w-0">
                  <span className="text-ink-subtle text-[10px] uppercase font-semibold truncate">
                    Commercial Scope & Terms
                  </span>
                  <button
                    type="button"
                    onClick={() => transitionToStage(3)}
                    className="inline-flex min-h-[48px] items-center gap-1 text-[11px] text-brand hover:underline cursor-pointer font-semibold shrink-0 px-2 py-1"
                  >
                    <Edit3 className="h-3.5 w-3.5 shrink-0" />
                    <span>Edit Scope</span>
                  </button>
                </div>
                <div className="space-y-1.5 text-ink-muted min-w-0 w-full">
                  <div className="min-w-0 break-words">
                    <span className="text-ink-subtle block text-[10px]">Product / Commodity Focus:</span>
                    <span className="text-ink font-medium break-words">{formData.productFocus || "—"}</span>
                  </div>
                  {(formData.quantity || formData.unitOfMeasurement) && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 min-w-0 w-full">
                      {formData.quantity && (
                        <div className="min-w-0 break-words">
                          <span className="text-ink-subtle block text-[10px]">Estimated Volume:</span>
                          <span className="text-ink font-medium break-words">{formData.quantity}</span>
                        </div>
                      )}
                      {formData.unitOfMeasurement && (
                        <div className="min-w-0 break-words">
                          <span className="text-ink-subtle block text-[10px]">Unit of Measure:</span>
                          <span className="text-ink font-medium break-words">{formData.unitOfMeasurement}</span>
                        </div>
                      )}
                    </div>
                  )}
                  {formData.specifications && (
                    <div className="min-w-0 w-full">
                      <span className="text-ink-subtle block text-[10px]">Technical Specifications:</span>
                      <p className="font-body text-xs text-ink-muted whitespace-pre-wrap eb-glass p-2.5 rounded-[2px] border border-line mt-0.5 break-words">
                        {formData.specifications}
                      </p>
                    </div>
                  )}
                  {formData.additionalNotes && (
                    <div className="min-w-0 w-full">
                      <span className="text-ink-subtle block text-[10px]">Commercial Remarks:</span>
                      <p className="font-body text-xs text-ink-muted whitespace-pre-wrap eb-glass p-2.5 rounded-[2px] border border-line mt-0.5 break-words">
                        {formData.additionalNotes}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Online Submission & Email Draft Disclosure */}
            <div className="rounded-[2px] border border-line eb-glass p-3 sm:p-3.5 space-y-1.5 text-xs shadow-sm w-full min-w-0 max-w-full">
              <div className="flex items-center gap-2 text-brand">
                <ShieldCheck className="h-4 w-4 shrink-0" />
                <span className="font-mono text-[10px] sm:text-[11px] font-semibold uppercase tracking-wider truncate">
                  Online Submission & Email Draft Options
                </span>
              </div>
              <p className="font-body text-[11px] text-ink-muted leading-relaxed break-words">
                Online RFQ submissions are sent to our backend and stored in PostgreSQL for administrative review. Choosing Open Email Application only opens a pre-filled draft in your email software; it does not send the message or submit or store an enquiry. Review and send the draft yourself if you choose that option.
              </p>
            </div>

            {/* Clipboard Fallback Container (revealed when clipboard write fails) */}
            {showClipboardFallback && (
              <div
                role="region"
                aria-label="Plain Text RFQ Summary Fallback"
                className="rounded-[2px] border border-brand/40 bg-brand-soft p-3 sm:p-3.5 space-y-2 text-xs animate-in fade-in duration-200 w-full min-w-0 max-w-full"
              >
                <div className="flex items-center justify-between text-brand gap-2 min-w-0">
                  <span className="font-mono text-[11px] font-semibold truncate">
                    Manual Copy Fallback (Clipboard Access Unavailable)
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      fallbackTextareaRef.current?.focus();
                      fallbackTextareaRef.current?.select();
                    }}
                    className="inline-flex min-h-[48px] items-center text-[10px] font-mono underline hover:text-brand-hover px-2 py-1 shrink-0"
                  >
                    Select All Text
                  </button>
                </div>
                <p className="text-[11px] text-ink-muted break-words">
                  Clipboard auto-copy was restricted by your browser. The plain-text RFQ draft below is pre-selected for manual copy (press Ctrl+C or Cmd+C):
                </p>
                <textarea
                  ref={fallbackTextareaRef}
                  value={rfqSummaryBody}
                  readOnly
                  rows={8}
                  className="w-full max-w-full rounded-[2px] border border-line-strong eb-glass p-2 sm:p-2.5 font-mono text-[10px] sm:text-[11px] text-ink focus:border-brand focus:outline-none"
                />
              </div>
            )}

            {/* Action CTAs */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2 w-full min-w-0">
              <button
                type="button"
                onClick={handleSubmitOnline}
                disabled={isSubmitting || !isOnline}
                className="w-full sm:w-auto inline-flex min-h-[48px] items-center justify-center gap-2 rounded-[2px] bg-brand px-4 sm:px-6 py-2.5 font-heading text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-brand-ink hover:bg-brand-hover transition-all cursor-pointer shadow-sm focus-visible:outline-2 focus-visible:outline-brand max-w-full min-w-0 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
                    <span className="truncate">Submitting RFQ...</span>
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4 shrink-0" />
                    <span className="truncate">Submit Official RFQ Online</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleOpenEmail}
                className="w-full sm:w-auto inline-flex min-h-[48px] items-center justify-center gap-2 rounded-[2px] border border-line-strong bg-panel px-4 sm:px-5 py-2.5 font-heading text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-ink-muted hover:border-brand hover:text-brand transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-brand shadow-sm max-w-full min-w-0"
              >
                <Mail className="h-4 w-4 shrink-0" />
                <span className="truncate">Open Email Application</span>
                <ExternalLink className="h-3.5 w-3.5 opacity-80 shrink-0" />
              </button>

              <button
                type="button"
                onClick={handleCopy}
                className="w-full sm:w-auto inline-flex min-h-[48px] items-center justify-center gap-2 rounded-[2px] border border-line-strong bg-panel px-4 sm:px-5 py-2.5 font-heading text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-ink-muted hover:border-brand hover:text-brand transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-brand shadow-sm max-w-full min-w-0"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4 text-[#059669] dark:text-[#10B981] shrink-0" />
                    <span className="text-[#059669] dark:text-[#10B981] truncate">RFQ Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4 text-ink-subtle shrink-0" />
                    <span className="truncate">Copy RFQ Summary</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleReset}
                className="w-full sm:w-auto inline-flex min-h-[48px] items-center justify-center gap-1.5 rounded-[2px] text-xs font-mono text-ink-subtle hover:text-ink transition-colors cursor-pointer sm:ml-auto px-3 max-w-full min-w-0"
              >
                <RotateCcw className="h-3.5 w-3.5 shrink-0" />
                <span>Reset Form</span>
              </button>
            </div>
          </>
        )}
      </div>
    )}
      </div>
    </div>
  );
}
