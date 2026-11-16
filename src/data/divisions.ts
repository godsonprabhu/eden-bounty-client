import { DivisionItem } from "@/types";

/**
 * Every division record, including ones no longer offered publicly.
 * Entries marked `active: false` are kept (never deleted) so historical enquiries that
 * reference their IDs still resolve in the admin console. IDs and codes must not change.
 */
export const allDivisions: DivisionItem[] = [
  {
    id: "mineral-water",
    code: "EB-DIV-01",
    name: "Mineral Water",
    sector: "Commercial Service",
    accentColor: "#0284C7",
    image: "/images/divisions/mineral-water.jpg",
    images: [
      "/images/services/mineral-water/refreshing-mineral-water-trio.png",
      "/images/services/mineral-water/refreshing-mineral-water-duo.png",
      "/images/services/mineral-water/mineral-water-refill-gallon.png",
    ],
    description:
      "Clean, safe drinking water from a protected source, bottled to national standards.",
    scopeFocus:
      "Natural mineral water and purified drinking water distribution in consumer bottles, bulk jugs, refill gallons, and catering cups.",
    href: "/services/mineral-water",
    highlights: [
      "Clean, safe drinking water from a protected source",
      "Bottled strictly to national standards",
      "Multiple packaging sizes from 200 ml cups to 19 L gallons",
      "Consistent mineral content and balanced pH range",
    ],
    capabilities: [
      "Palletized wholesale handling and scheduled regional dispatch",
      "Multiple packaging formats: 200 ml, 330 ml, 500 ml, 600 ml, 1.5 L, 5 L, and 19 L",
      "Clean and protected natural water source bottling",
      "Wholesale supply contracts for corporate, retail, and hospitality buyers",
    ],
    productOfferings: [
      "Natural mineral water",
      "Purified drinking water",
      "Alkaline water",
      "Sparkling water",
    ],
    packagingOptions: [
      "330 ml bottles",
      "500 ml bottles",
      "600 ml bottles",
      "1.5 L bottles",
      "5 L jugs",
      "19 L refill gallons",
      "200 ml cups",
    ],
    specifications: [
      { label: "Typical pH Range", value: "pH 6.5 to 8.5" },
      { label: "Mineral Content", value: "Calcium, magnesium, sodium stated on label" },
      { label: "Source Standard", value: "Clean, safe drinking water from protected source" },
      { label: "Production Standard", value: "Bottled to national standards" },
    ],
    targetCustomers: [
      "Retailers & supermarkets",
      "Restaurants & cafes",
      "Hotels & hospitality venues",
      "Offices & corporate facilities",
      "Event organisers",
      "Commercial beverage distributors",
    ],
    applications: [
      "Commercial hospitality, hotel chains, and resort procurement",
      "Corporate offices, executive centers, and regional facilities",
      "Institutional dining facilities and large-scale event catering",
      "Wholesale FMCG retail distribution and export consolidators",
    ],
  },
  {
    id: "scrap-trading",
    code: "EB-DIV-02",
    name: "Scrap Trading",
    sector: "Commercial Service",
    accentColor: "#64748B",
    image: "/images/divisions/scrap-trading.jpg",
    images: [
      "/images/services/scrap-trading/industrial-steel-recycling-yard.png",
      "/images/services/scrap-trading/industrial-recycling-yard-sunset.png",
      "/images/services/scrap-trading/non-ferrous-metals-recycling-yard.png",
    ],
    description:
      "Purchase, sorting and supply of recyclable metals to mills, smelters and recyclers.",
    scopeFocus:
      "Graded ferrous and non-ferrous recyclable metals supplied by the tonne or container load with official weighbridge documentation.",
    href: "/services/scrap-trading",
    highlights: [
      "Purchase, sorting, and supply of recyclable metals",
      "Comprehensive ferrous and non-ferrous metal portfolios",
      "Graded strictly to recognised scrap specifications (e.g. ISRI)",
      "Supplied by the tonne or container load with weighbridge certificates",
    ],
    capabilities: [
      "Industrial yard sorting, sizing, and grading infrastructure",
      "Standardised grading under recognised scrap specifications (e.g. ISRI)",
      "Container load and bulk vessel logistics coordination",
      "Official weighbridge certificates and transparent commercial documentation",
    ],
    subcategories: [
      {
        title: "Ferrous Metals",
        description: "Recyclable iron and steel materials prepared for furnace charging.",
        items: [
          "HMS 1 and 2 (heavy melting steel)",
          "Shredded scrap",
          "Cast iron",
          "Rebar offcuts",
        ],
      },
      {
        title: "Non-Ferrous Metals",
        description: "High-value secondary non-ferrous metals and clean alloys.",
        items: [
          "Copper (bare bright, millberry)",
          "Aluminium (extrusion, cast, cans)",
          "Brass",
          "Stainless steel",
          "Lead",
        ],
      },
      {
        title: "Other Recyclables",
        description: "Secondary industrial scrap and utility materials.",
        items: [
          "Used cables",
          "Used rails",
          "Paper and plastic scrap (if applicable)",
        ],
      },
    ],
    packagingOptions: [
      "Supplied by the metric tonne",
      "Full container load (FCL) consignments",
      "Bulk loose cargo with weighbridge certificates",
    ],
    specifications: [
      { label: "Grading Standard", value: "Recognised scrap specifications (e.g. ISRI)" },
      { label: "Supply Terms", value: "By the tonne or container load" },
      { label: "Verification", value: "Official weighbridge certificates" },
      { label: "Primary Ferrous", value: "HMS 1 and 2, shredded scrap, cast iron, rebar offcuts" },
      { label: "Primary Non-Ferrous", value: "Copper (bare bright, millberry), aluminium, brass, stainless steel, lead" },
    ],
    targetCustomers: [
      "Steel mills & EAF operators",
      "Foundries & metal smelters",
      "Metal recyclers & processors",
      "Commodity exporters",
    ],
    applications: [
      "Electric arc furnace (EAF) steelmaking plants and mini-mills",
      "Secondary copper smelting and non-ferrous refining facilities",
      "Foundry ingot manufacturing and industrial recycling operations",
      "International circular economy commodity re-export trading",
    ],
  },
  {
    id: "construction",
    code: "EB-DIV-03",
    name: "Construction / Building Promotion",
    sector: "Commercial Service",
    accentColor: "#D97706",
    image: "/images/divisions/construction.jpg",
    images: [
      "/images/services/construction/modern-villa-development-sunset.png",
      "/images/services/construction/modern-villa-blueprint-sunset.png",
      "/images/services/construction/sunset-construction-site-engineers.png",
    ],
    description:
      "Development and promotion of residential, commercial and industrial properties, plus building and contracting services.",
    scopeFocus:
      "Comprehensive building contracting, property development, architectural fit-out, project management, and commercial unit sales promotion.",
    href: "/services/construction",
    highlights: [
      "Property development and building promotion",
      "General construction and contracting services",
      "Renovation and interior fit-out capabilities",
      "Full project management from concept to sales and marketing of units",
    ],
    capabilities: [
      "Turnkey property development across residential, commercial, and industrial sectors",
      "General building contracting and engineering execution",
      "Commercial renovation and specialized fit-out works",
      "Project management and sales and marketing of completed units",
    ],
    productOfferings: [
      "Property development",
      "General construction",
      "Renovation and fit-out",
      "Project management",
      "Sales and marketing of units",
    ],
    packagingOptions: [
      "Terrace and landed homes",
      "Condominiums and apartments",
      "Commercial shop lots",
      "Industrial factories and warehouses",
    ],
    specifications: [
      { label: "Service Scope", value: "Property development, building contracting, and project management" },
      { label: "Contracting Services", value: "General construction, renovation, and fit-out" },
      { label: "Promotion Services", value: "Sales and marketing of residential, commercial, and industrial units" },
      { label: "Residential Projects", value: "Terrace and landed homes, condominiums and apartments" },
      { label: "Commercial / Industrial", value: "Shop lots, factories and warehouses" },
    ],
    targetCustomers: [
      "Property buyers & residential owners",
      "Commercial tenants & retail operators",
      "Industrial logistics firms & factory owners",
      "Real estate developers & corporate investors",
    ],
    applications: [
      "Residential landed schemes, condominiums, and apartment developments",
      "Commercial retail shop lots, corporate offices, and mixed-use complexes",
      "Industrial manufacturing factories, logistics parks, and warehouse facilities",
      "Turnkey property renovation, architectural fit-out, and marketing promotion",
    ],
  },
  {
    id: "shisha-tobacco-trading",
    code: "EB-DIV-05",
    name: "Shisha Tobacco Trading",
    // Withdrawn from the public site per client instruction. Retained for historical enquiries.
    active: false,
    sector: "Commercial Service",
    accentColor: "#B45309",
    image: "/images/divisions/shisha-tobacco.jpg",
    description: "Flavoured tobacco trading. (Historical catalog reference).",
    scopeFocus: "Historical division records only.",
    href: "/services/shisha-tobacco-trading",
  },
  {
    id: "axe-oil",
    code: "EB-DIV-06",
    name: "Axe Oil",
    // Withdrawn from the public site per client instruction. Retained for historical enquiries.
    active: false,
    sector: "Commercial Service",
    accentColor: "#0D9488",
    image: "/images/divisions/axe-oil.jpg",
    description: "Medicated oil trading. (Historical catalog reference).",
    scopeFocus: "Historical division records only.",
    href: "/services/axe-oil",
  },
  {
    id: "petroleum-products",
    code: "EB-DIV-07",
    name: "Petroleum Products",
    sector: "Commercial Service",
    accentColor: "#D4AF37",
    image: "/images/divisions/petroleum-products.jpg",
    images: [
      "/images/services/petroleum-products/petroleum-products-fuel-bulk-lubricants.png",
      "/images/services/petroleum-products/petroleum-supply-triptych-1.png",
      "/images/services/petroleum-products/petroleum-supply-triptych-2.png",
    ],
    description:
      "Supply of fuels and refined distillates for industry, transport and commercial use.",
    scopeFocus:
      "Commercial supply of diesel, petrol, kerosene, LPG, and bitumen with delivery quality certificates and commercial credit terms.",
    href: "/services/petroleum-products",
    highlights: [
      "Supply of diesel (Euro 5), petrol (RON 95 and 97), kerosene, LPG and bitumen",
      "Bulk tanker deliveries, drum and IBC supply, and depot collection",
      "Quality certificates accompanying every consignment",
      "High delivery reliability and structured commercial credit terms",
    ],
    capabilities: [
      "Coordinated bulk road tanker logistics for industrial facilities",
      "Drum and Intermediate Bulk Container (IBC) packaging and dispatch",
      "Terminal and depot collection facilities",
      "Structured commercial credit terms and documented quality assurance",
    ],
    productOfferings: [
      "Diesel (Euro 5)",
      "Petrol (RON 95 and 97)",
      "Kerosene",
      "Liquefied Petroleum Gas (LPG)",
      "Bitumen",
    ],
    packagingOptions: [
      "Bulk tanker deliveries",
      "Industrial drum supply (200L)",
      "Intermediate Bulk Container (IBC 1000L)",
      "Depot collection",
    ],
    specifications: [
      { label: "Primary Fuels", value: "Diesel (Euro 5), Petrol (RON 95 and RON 97)" },
      { label: "Specialty Distillates", value: "Kerosene, Liquefied Petroleum Gas (LPG), Bitumen" },
      { label: "Supply Modes", value: "Bulk tanker deliveries, drum and IBC supply, depot collection" },
      { label: "Quality Assurance", value: "Quality certificates provided per delivery" },
      { label: "Commercial Terms", value: "Delivery reliability, credit terms for qualified corporate accounts" },
    ],
    targetCustomers: [
      "Industrial manufacturing factories",
      "Fleet & logistics transport operators",
      "Construction & infrastructure firms",
      "Marine & power generation users",
    ],
    applications: [
      "Commercial transport fleets, logistics hauliers, and heavy machinery",
      "Manufacturing plant power systems, steam boilers, and processing plants",
      "Civil infrastructure construction, road surfacing, and bitumen paving",
      "Marine coastal transport and standby generator installations",
    ],
  },
  {
    id: "lubricants",
    code: "EB-DIV-08",
    name: "Lubricants",
    // Removed from the public site (CR-C1). Retained for historical enquiries.
    active: false,
    sector: "Commercial Service",
    accentColor: "#EA580C",
    image: "/images/divisions/lubricants.jpg",
    description:
      "Industrial and automotive lubricants. (Historical catalog reference).",
    scopeFocus:
      "Historical division records only.",
    href: "/services/lubricants",
  },
  {
    id: "furnace-oil",
    code: "EB-DIV-09",
    name: "Furnace Oil",
    sector: "Commercial Service",
    accentColor: "#6366F1",
    image: "/images/divisions/furnace-oil.jpg",
    images: [
      "/images/services/furnace-oil/furnace-oil-refinery-sunset.png",
      "/images/services/furnace-oil/furnace-oil-at-sunset-refinery.png",
      "/images/services/furnace-oil/industrial-furnace-oil-plant.png",
    ],
    description:
      "Heavy residual fuel oil burned in industrial furnaces, boilers, kilns and power generation.",
    scopeFocus:
      "Supply of low and high sulphur fuel oils and viscosity grades (180 cSt and 380 cSt) with heated storage and pumping coordination.",
    href: "/services/furnace-oil",
    highlights: [
      "Heavy residual fuel oil for industrial furnaces, boilers and kilns",
      "Low sulphur (LSFO) and high sulphur (HSFO) grades",
      "Viscosity grades including 180 cSt and 380 cSt",
      "Bulk tanker, ISO tank, and marine barge supply modes",
    ],
    capabilities: [
      "Bulk delivery via road tanker fleet, ISO tanks, and coastal barges",
      "Viscosity grades supplied to match industrial burner specifications",
      "Coordinated delivery scheduling for continuous manufacturing plants",
      "Technical guidance on heated storage and specialized pumping requirements",
    ],
    productOfferings: [
      "Low Sulphur Fuel Oil (LSFO)",
      "High Sulphur Fuel Oil (HSFO)",
      "180 cSt Viscosity Grade",
      "380 cSt Viscosity Grade",
    ],
    specifications: [
      { label: "Typical Density", value: "About 0.95 to 1.0 kg/L" },
      { label: "Typical Flash Point", value: "At least 60°C" },
      { label: "Typical Calorific Value", value: "About 10,000 to 10,500 kcal/kg" },
      { label: "Sulphur Content", value: "Stated per commercial grade (LSFO / HSFO)" },
      { label: "Common Viscosity", value: "180 cSt and 380 cSt" },
    ],
    packagingOptions: [
      "Bulk tanker deliveries",
      "ISO tank containers",
      "Marine barge delivery for coastal users",
    ],
    handlingNotes:
      "Handling note: Furnace oil requires heated storage and pumping infrastructure because it is viscous.",
    targetCustomers: [
      "Manufacturing & industrial plants",
      "Power producers & utilities",
      "Cement & steel plants",
      "Shipping & marine companies",
    ],
    applications: [
      "Steel re-rolling mills, smelting works, and aluminum foundries",
      "Industrial glass, ceramic, and clay brick manufacturing kilns",
      "Commercial steam boilers and centralized district heating plants",
      "Marine auxiliary boilers and bunkering operations",
    ],
  },
  {
    id: "agricultural-drones",
    code: "EB-DIV-10",
    name: "Drone Solutions",
    sector: "Commercial Service",
    accentColor: "#00E5FF",
    image: "/images/divisions/agricultural-drones.jpg",
    images: [
      "/images/services/agricultural-drones/agricultural-industrial-drone-operations.png",
      "/images/services/agricultural-drones/agricultural-security-drone-operations.png",
      "/images/services/agricultural-drones/agricultural-surveillance-drones.png",
    ],
    description:
      "Drones for agriculture and surveillance solutions.",
    scopeFocus:
      "Supply of specialized unmanned aerial systems for crop spraying, broadcast seeding, field mapping, and high-resolution site surveillance.",
    href: "/services/agricultural-drones",
    highlights: [
      "Agricultural drones for crop spraying, seeding, and health monitoring",
      "Surveillance drones for perimeter security and infrastructure inspection",
      "Tank capacities from 10 to 40 L with GPS and RTK precision",
      "4K optical zoom and thermal imaging options for security operations",
    ],
    capabilities: [
      "Turnkey commercial drone equipment supply and operator documentation",
      "Agricultural UAV setups with tank capacities from 10 to 40 L",
      "Centimeter-accurate GPS or RTK autonomous flight navigation",
      "Surveillance UAV platforms with optical zoom and thermal sensor integration",
    ],
    subcategories: [
      {
        title: "Agricultural Drones",
        description:
          "Heavy-duty aerial robotics for precision crop management, nutrient distribution, and large-scale agricultural mapping.",
        items: [
          "Crop spraying (pesticide, fertiliser)",
          "Seeding and granular broadcasting",
          "Field mapping and topographical surveys",
          "Crop health and vegetation index monitoring",
        ],
        specs: [
          { label: "Tank Capacity", value: "10 to 40 L" },
          { label: "Spray Coverage", value: "Roughly 10 to 25 hectares per hour" },
          { label: "Flight Time", value: "10 to 20 minutes per charge when loaded" },
          { label: "Navigation Precision", value: "GPS or RTK precision" },
          { label: "Applicable Crops", value: "Palm oil, rice, vegetables, orchards" },
        ],
        benefits: [
          "Less manual labour required for field operations",
          "Even and consistent spray distribution across dense canopies",
          "Reduced chemical use through targeted micro-droplet application",
        ],
      },
      {
        title: "Surveillance Drones",
        description:
          "Long-range autonomous aerial platforms for facility security, infrastructure inspection, and emergency oversight.",
        items: [
          "Perimeter and site security",
          "Infrastructure inspection",
          "Search and rescue operations",
          "Event monitoring",
        ],
        specs: [
          { label: "Camera & Sensor", value: "4K camera with optical zoom, thermal imaging option" },
          { label: "Flight Time", value: "30 to 45 minutes" },
          { label: "Operating Range", value: "Several kilometres" },
          { label: "Video Telemetry", value: "Live video feed" },
        ],
      },
    ],
    specifications: [
      { label: "Agricultural Tank Capacity", value: "10 to 40 L" },
      { label: "Spray Coverage", value: "Roughly 10 to 25 hectares per hour" },
      { label: "Agricultural Flight Time", value: "10 to 20 minutes per charge when loaded" },
      { label: "Navigation Precision", value: "GPS or RTK precision" },
      { label: "Surveillance Camera", value: "4K camera with optical zoom, thermal imaging option" },
      { label: "Surveillance Flight Time", value: "30 to 45 minutes" },
      { label: "Surveillance Range", value: "Several kilometres with live video feed" },
    ],
    targetCustomers: [
      "Plantations & agricultural estates",
      "Factories & industrial facilities",
      "Construction sites & infrastructure projects",
      "Corporate security firms",
    ],
    applications: [
      "Palm oil, rice, vegetable, and orchard precision crop spraying",
      "Broadcast seeding and aerial nutrient distribution",
      "Industrial facility perimeter security and asset protection",
      "Construction site progression monitoring and infrastructure inspection",
    ],
  },
];

/** Divisions currently offered on the public site and in the RFQ form. */
export const businessDivisions: DivisionItem[] = allDivisions.filter((d) => d.active !== false);
