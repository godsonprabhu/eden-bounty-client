/** Commercial workflow — sourced from the company's existing published process copy. */
export const tradeWorkflow = [
  {
    step: "01",
    title: "Enquiry intake & scoping",
    description:
      "Commercial inquiries are received through the official business email and reviewed based on confirmed wholesale parameters across the commercial divisions.",
    points: [
      "Formal inquiry parameter intake and quantity scoping",
      "Commercial trade routing across relevant business divisions",
      "Direct correspondence tracking for registered commercial entities",
    ],
  },
  {
    step: "02",
    title: "Specification & sourcing review",
    description:
      "Commercial review of requested product specifications, availability, and manufacturer documentation prior to trade commitment.",
    points: [
      "Review of technical specifications and commercial parameters",
      "Evaluation of product availability and commercial documentation",
      "Manufacturer authorisation is subject to direct written confirmation",
    ],
  },
  {
    step: "03",
    title: "Documented terms & quotation",
    description:
      "Formulation of formal commercial quotations, documented transaction terms, and clear commercial compliance parameters.",
    points: [
      "Formal commercial quotations prepared under documented terms",
      "Transparent commercial conditions and payment parameters",
      "Documented mutual agreement prior to trade confirmation",
    ],
  },
  {
    step: "04",
    title: "Trade coordination",
    description:
      "Structured commercial communication and trade coordination between counterparties through the official business email.",
    points: [
      "Structured trade correspondence and coordination",
      "Commercial milestone updates via official business email",
      "Commercial confidentiality maintained for all correspondence",
    ],
  },
];

/** Division clusters used for enquiry routing (from the existing RFQ console). */
export const divisionClusters = [
  {
    code: "EB-SECTOR-01",
    category: "Energy & Hydrocarbons",
    sectors: ["Petroleum Products", "Furnace Oil"],
    defaultDivisionId: "petroleum-products",
  },
  {
    code: "EB-SECTOR-02",
    category: "Industrial & Materials",
    sectors: ["Scrap Trading", "Construction / Building Promotion"],
    defaultDivisionId: "scrap-trading",
  },
  {
    code: "EB-SECTOR-03",
    category: "Consumer Goods",
    sectors: ["Mineral Water"],
    defaultDivisionId: "mineral-water",
  },
  {
    code: "EB-SECTOR-04",
    category: "Drone Solutions",
    sectors: ["Drone Solutions"],
    defaultDivisionId: "agricultural-drones",
  },
];
