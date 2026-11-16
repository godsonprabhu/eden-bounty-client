# Design System Master File: EIDEN BOUNTY

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.  
> If that file exists, its rules **override** this Master file.  
> If not, strictly follow the rules below.

---

**Project:** Eiden Bounty  
**Design Direction:** Concept 1: The Sovereign Meridian (International Corporate) with Technical Elements from Concept 2 (The Kinetic Monolith)  
**Style Framework:** Minimalism & Swiss Modernism 2.0 + High-Precision Industrial Telemetry  
**Design Dials:** Variance 6/10 (Balanced / Modern) | Motion 3/10 (Subtle & Controlled) | Density 5/10 (Standard Institutional)  
**Single Source of Truth:** `assets/design-tokens.json` $\rightarrow$ `assets/design-tokens.css` $\rightarrow$ `assets/design-tokens.tailwind.js`

---

## 1. Global Rules & Color Palette

### Approved Corporate Palette

| Role | Hex | On-Color | CSS Variable | Usage |
|------|-----|----------|--------------|-------|
| **Primary (Maritime Navy)** | `#0A1118` | `#FFFFFF` | `--color-primary` | Dominant dark canvas, executive headers, primary container shells |
| **Secondary (Institutional Slate)** | `#1E293B` | `#FFFFFF` | `--color-secondary` | Elevated structural panels, secondary navigation, table headers |
| **Accent (Sovereign Gold)** | `#C5A880` | `#0A1118` | `--color-accent` | Brand insignia, executive focus rings, primary action triggers, status anchors |
| **Technical (Electric Cyan)** | `#00E5FF` | `#0A1118` | `--color-technical` | Autonomous agritech indicators, flight telemetry vectors, data coordinates |
| **Background (Architectural Off-White)**| `#F8FAFC` | `#0A1118` | `--color-background` | Primary light page background, clean reading substrate |
| **Foreground (Deep Navy Text)** | `#0A1118` | `#F8FAFC` | `--color-foreground` | High-contrast body typography, principal headlines |
| **Card (Pure White)** | `#FFFFFF` | `#0A1118` | `--color-card` | Surface containers, technical document cards |
| **Muted Canvas** | `#F1F5F9` | `#64748B` | `--color-muted` | Inactive tabs, secondary pill badges, alternate table rows |
| **Border Light** | `#E2E8F0` | — | `--color-border` | Hairline 1px structural grid dividers (light mode) |
| **Border Dark / Technical** | `#334155` | — | `--color-border-technical` | Structural frame boundaries (dark surfaces) |
| **Ring / Focus** | `#C5A880` | — | `--color-ring` | 2px visible keyboard accessibility focus rings |

### Contrast Compliance (WCAG 2.1 AA / AAA)
- **Primary Text (`#0A1118`) on Background (`#F8FAFC`)**: Contrast ratio `17.4:1` (Exceeds WCAG AAA `7:1`).
- **Sovereign Gold (`#C5A880`) on Maritime Navy (`#0A1118`)**: Contrast ratio `7.8:1` (Exceeds WCAG AAA `7:1`).
- **Electric Cyan (`#00E5FF`) on Maritime Navy (`#0A1118`)**: Contrast ratio `11.9:1` (Exceeds WCAG AAA `7:1`).
- **Muted Text (`#64748B`) on Background (`#F8FAFC`)**: Contrast ratio `4.6:1` (Exceeds WCAG AA `4.5:1`).

---

## 2. Typography System

### Typography Stack
- **Headings & Display:** `Lexend`, `Cabinet Grotesk`, -apple-system, sans-serif
- **Body & Longform:** `Source Sans 3`, -apple-system, sans-serif
- **Technical & Metadata:** `JetBrains Mono`, `Fira Code`, monospace

### Google Fonts Import
```css
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Lexend:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');
```

### Scale & Hierarchy Table

| Token | Size | Line Height | Letter Spacing | Weight | Typical Element |
|-------|------|-------------|----------------|--------|-----------------|
| `--text-hero` | `4.5rem` (72px) | `1.05` | `-0.03em` | 700 Bold | Main Landing Headline |
| `--text-h1` | `3.0rem` (48px) | `1.15` | `-0.025em` | 700 Bold | Section Hero Titles |
| `--text-h2` | `2.25rem` (36px) | `1.20` | `-0.02em` | 600 SemiBold | Division Names, Major Features |
| `--text-h3` | `1.5rem` (24px) | `1.30` | `-0.015em` | 600 SemiBold | Component Titles, Dossier Headers |
| `--text-lead` | `1.25rem` (20px) | `1.50` | `0` | 400 Regular | Lead Paragraphs |
| `--text-base` | `1.0rem` (16px) | `1.65` | `0` | 400 Regular | Standard Body Copy |
| `--text-sm` | `0.875rem` (14px) | `1.50` | `+0.01em` | 500 Medium | Table Cells, Captions, Labels |
| `--text-mono` | `0.75rem` (12px) | `1.40` | `+0.12em` | 500 Medium | HS Codes, Telemetry, Coordinates |

---

## 3. Spacing & Grid System

Base unit: **8px** (Micro increments: **4px**)

| Token | Pixel Value | Rem Value | Core Application |
|-------|-------------|-----------|------------------|
| `--space-1` | `4px` | `0.25rem` | Micro padding, hairline gaps |
| `--space-2` | `8px` | `0.5rem` | Icon-to-text spacing, compact badge insets |
| `--space-3` | `12px` | `0.75rem` | Input field vertical padding, small gaps |
| `--space-4` | `16px` | `1.0rem` | Card padding (mobile), standard element gaps |
| `--space-6` | `24px` | `1.5rem` | Card padding (desktop), grid gutters |
| `--space-8` | `32px` | `2.0rem` | Component stack separation |
| `--space-12` | `48px` | `3.0rem` | Sub-section spacing |
| `--space-16` | `64px` | `4.0rem` | Section vertical rhythm |
| `--space-24` | `96px` | `6.0rem` | Major corporate divider padding |
| `--space-32` | `128px` | `8.0rem` | Hero top/bottom buffer zones |

### Breakpoint Matrix
- `sm`: `640px` (Compact mobile / landscape)
- `md`: `768px` (Tablet portrait)
- `lg`: `1024px` (Tablet landscape / compact laptop)
- `xl`: `1280px` (Standard desktop monitor)
- `2xl`: `1536px` (Ultra-wide corporate display)

---

## 4. Radii, Borders & Surface Elevation

### Border Radii Discipline
Precision industrial styling mandates clean, architectural geometry:
- **`--radius-none`:** `0px` — Full-bleed sections, strict table cells, divider bars.
- **`--radius-sm`:** `2px` — Monospaced technical tags, coordinate chips, secondary buttons.
- **`--radius-md`:** `4px` — Primary interactive buttons, input controls, card containers.
- **`--radius-lg`:** `6px` — Large flyouts, interactive division dossiers.
- *Strict Proscription:* No pill-shaped bubbles (`rounded-3xl` / `rounded-full` prohibited for cards or content panels).

### Shadows & Elevation
- **`--shadow-none`:** `none`
- **`--shadow-sm`:** `0 1px 2px 0 rgba(10, 17, 24, 0.05)`
- **`--shadow-md`:** `0 4px 6px -1px rgba(10, 17, 24, 0.1), 0 2px 4px -2px rgba(10, 17, 24, 0.06)`
- **`--shadow-lg`:** `0 10px 15px -3px rgba(10, 17, 24, 0.12), 0 4px 6px -4px rgba(10, 17, 24, 0.08)`
- **`--shadow-technical`:** `0 0 0 1px #1E293B, 0 8px 24px -4px rgba(10, 17, 24, 0.3)`
- **`--shadow-cyan-glow`:** `0 0 16px rgba(0, 229, 255, 0.25)`

---

## 5. Component Principles

### Primary Corporate Button
- Height: `44px` (touch target compliant).
- Background: `--color-primary` (`#0A1118`).
- Text: `--color-on-primary` (`#FFFFFF`), `font-weight: 600`, `letter-spacing: 0.01em`.
- Border: `1px solid var(--color-accent)` (`#C5A880`).
- Border Radius: `4px` (`rounded-sm`).
- Hover: Background `#111C27`, border `#D4BE9F`, transition `200ms easeOutExpo`.
- Focus: `outline: 2px solid var(--color-accent)`, `outline-offset: 2px`.

### Technical RFQ / Action Trigger
- Height: `44px`.
- Background: `--color-accent` (`#C5A880`).
- Text: `--color-primary` (`#0A1118`), `font-weight: 700`.
- Hover: Background `#D4BE9F`.

### Division Dossier Card
- Background: `#FFFFFF` (Light) / `#1E293B` (Dark).
- Border: `1px solid var(--color-border)` (`#E2E8F0` / `#334155`).
- Corner Accent: 1px top-left coordinate mark in Sovereign Gold (`#C5A880`).
- Monospaced Header: `[EB-DIV-XX]` in JetBrains Mono (`0.75rem`, uppercase).

---

## 6. Motion & Interaction Principles

- **Scroll Reveal (Subtle):**
  - Trigger: Viewport entry at 90%.
  - Duration: `350ms`.
  - Offset: Small vertical translation (`y: 12px`, never excessive jumps).
  - Curve: `cubic-bezier(0.16, 1, 0.3, 1)` (easeOutExpo).
- **Reduced Motion:**
  - When `prefers-reduced-motion: reduce` is detected, animations collapse to `duration: 0s` with immediate static final rendering.

---

## 7. Division Architecture & Visual Codes

| Division Code | Division Title | Primary Sector | Color Accent | Technical Spec Focus |
| :--- | :--- | :--- | :--- | :--- |
| `[EB-DIV-01]` | Mineral Water | Bulk FMCG Bottling | Azure `#0284C7` | TDS, pH, Sanitary Filling Standards |
| `[EB-DIV-02]` | Scrap Trading | Secondary Metallurgy | Steel `#475569` | ISRI HMS 1/2, Metric Tonnage, Origin |
| `[EB-DIV-03]` | Construction | Structural Civil Works | Earth Amber `#D97706`| ASTM Steel, BS EN Standards, Aggregate |
| `[EB-DIV-04]` | Building Promotions | Commercial Real Estate | Bronze `#92400E` | GFA, Peninsular Hubs, Asset Logistics |
| `[EB-DIV-05]` | Shisha Tobacco | Regulated Wholesale | Tobacco `#B45309` | Cut Width, Moisture %, HS Codes |
| `[EB-DIV-06]` | Petroleum Products | Hydrocarbon Wholesale | Fuel Gold `#D4AF37` | Flash Point, Sulfur ppm, Bulk Parcels |
| `[EB-DIV-07]` | Axe Oil | Medicated Wellness | Camphor `#0D9488` | Active Camphor %, Export Container Manifest |
| `[EB-DIV-08]` | Industrial Lubricants| Machine & Turbine Fluids| High-Visc `#EA580C`| ISO VG 32-220, Viscosity Index, EP Rating |
| `[EB-DIV-09]` | Furnace Oil | Industrial Thermal Fuel | Russet `#C2410C` | CST @ 50°C, GCV kcal/kg, Marine Bunker |
| `[EB-DIV-10]` | Agricultural Drones | Autonomous Agritech | Cyan `#00E5FF` | Payload L/ha, RTK GPS, Spray Swath |

*Legal Disclosure Note on Agricultural Drones:*  
In compliance with verified documentation rules, division 10 denotes commercial distribution in association with Garuda Aerospace Limited; no unverified claims of exclusive global partnership or unverified holding stakes are permitted.

---

## 8. Anti-Patterns (Strictly Prohibited)

- ❌ **No generic SaaS marketing clichés** ("AI-driven synergy", "Disrupting trade").
- ❌ **No fabricated metrics or placeholder statistics** (e.g. "99.9% client happiness", "10,000 ships sailed").
- ❌ **No low-contrast grey text** (Body text must meet or exceed 4.5:1 WCAG AA).
- ❌ **No excessive glassmorphism or floating translucent cards**.
- ❌ **No unstyled native outlines** (always use `--color-ring` with visible offset).
- ❌ **No emoji icons** (use vector SVG from Lucide/Phosphor).
