# BAESS Labs — Platform Documentation

**Product name:** BAESS Labs (“BAESS”)  
**Primary URL:** https://baess.app  
**Stack (high level):** React (Vite), TypeScript, Tailwind CSS, shadcn/ui, Supabase (auth, database, edge functions), TanStack Query, Three.js / React Three Fiber (3D), Leaflet & Google Maps, Chart.js / Recharts / Plotly, jsPDF & html2canvas (reports), payments via Dodo Payments (where configured).

This document describes the **features implemented in the codebase** as of the repository state it was generated from, plus **positioning** relative to common industry tools. It is not a legal warranty of fitness for any particular engineering sign-off; always verify critical designs against local codes, independent engineering review, and manufacturer data.

---

## 1. Executive summary

BAESS Labs is a **browser-based solar engineering and business platform** that combines:

- **End-to-end PV workflow** from geolocated inputs and component selection through DC/AC design, losses, yield, BOQ, and financials.
- **Dedicated 3D PV design** on satellite-derived building geometry (positioned as a Helioscope-style workflow inside the same product).
- **BESS (battery) design** with load profiles, sizing, cables, optional DG hybrid paths, BOQ, costing, and financials.
- **AI-assisted** BOQ, feasibility-style reporting, chat-based solar calculations, and credit-metered usage.
- A large **free public calculator hub** for SEO, education, and lead generation.
- **Sandbox** experimental apps, **blog** (CMS-style via Supabase), **forum**, **reviews**, and marketing/documentation pages.

The platform’s strategic angle is **breadth + accessibility**: one login and one web experience spanning tools that are often split across desktop yield software, CAD plugins, CRM design suites, and separate spreadsheets.

---

## 2. Information architecture & routing

### 2.1 Public (no login)

| Path | Purpose |
|------|---------|
| `/` | Marketing homepage, pricing cues, navigation |
| `/auth`, `/auth/callback`, `/forgot-password`, `/reset-password` | Authentication |
| `/tools` | Hub listing all free engineering calculators |
| `/tools/*` | Individual free tools (see §6) |
| `/blog`, `/blog/:slug` | Blog listing and post pages (Supabase-backed) |
| `/forum`, `/forum/topic/:slug` | Community forum (read); new topic may require auth |
| `/documentation` | Documentation center (structured UI) |
| `/integrations` | Integrations overview (PVWatts, Maps, AI providers, etc.) |
| `/about`, `/careers`, `/faq`, `/contact`, `/reviews` | Company & support |
| `/privacy`, `/terms` | Legal |
| `/changelog` | Product changelog |
| `/products`, `/products/pv-designer`, `/products/bess-designer` | SEO product landing pages |

### 2.2 Authenticated (typical subscription / trial)

| Path | Purpose |
|------|---------|
| `/dashboard` | Central hub: AI tools, saved Advanced Calculator projects, legacy solar projects |
| `/advanced-calculator` | **PV AI Designer Pro** — main advanced PV design workspace (`?projectId=` for saved state) |
| `/pv-3d-designer` | **PV 3D Designer** — map + 3D building + module placement |
| `/solar-calculator`, `/calculator` | **Solar Simulator** — streamlined `SolarCalculator` flow (alias routes) |
| `/bess-designer` | **BESS Designer** |
| `/boq-generator` | Standalone **AI BOQ Generator** (chat + form + results) |
| `/solar-components` | **Solar Components Library** (panels/inverters; admin import tools) |
| `/solar-ai-chat` | **Solar AI Chat** — task-based AI calculations with artifacts & export |
| `/sandbox`, `/sandbox/apps/solar-eda`, `/sandbox/apps/solar-ai-diagnostics` | Sandbox mini-apps |
| `/account` | Profile, **subscription & billing**, **AI credit** balance and history |
| `/subscription/success` | Post-checkout success |
| `/project/:projectId` | **Project details** for legacy per-project `SolarCalculator` data |
| `/blog/admin`, `/blog/admin/create`, `/blog/admin/edit/:id` | Blog administration |
| `/forum/new` | Create forum topic |
| `/admin` | Admin dashboard (restricted) |

---

## 3. Core products (main applications)

### 3.1 PV AI Designer Pro (`/advanced-calculator`)

**Role:** Primary professional PV design application — tabbed workflow from location to AI deliverables.

**Main tabs (user-facing):**

1. **Location** — Project naming, geolocation, timezone, and site context (with `LocationInputs`).
2. **PV Select** — `ComponentSelector`: real module/inverter catalog linkage from the app’s data layer.
3. **PV Areas** — `AreaCalculator`: map-based polygons, structure types, **3D building** tooling, **CAD-oriented layout** (`CadLayoutSection`), **shading** configuration, **electrical** overlays (string routing concepts), distance tools, module placement; integrates with capacity and array geometry for downstream calculations.
4. **DC Config** — String sizing variants (`StringSizingCalculator`, `EnhancedStringSizingCalculator`, `DCStringSizingCalculator`), central inverter flows (`CentralInverterStringSizing`), DCDB sizing (`DCDBSizingCalculator`), DC cable sizing (`DCDBCableSizing`), combiner/BOS logic as implemented.
5. **AC Config** — `ACSideConfiguration`: LV and HV architectures, combiners, IDT, power transformer, breaker and cable selections with structured sections; feeds BOQ mapping logic in code.
6. **Design Summary** — Consolidated design snapshot.
7. **Losses** — `DetailedLossesConfiguration` for nuanced PR / loss modeling.
8. **Results** — Production views (`ProductionResults`, `EfficiencyAdjustment`, energy engine hooks including **PVWatts**-based paths where used).
9. **AI BOQ** — `DetailedBOQGenerator` / related BOQ stack with AI parameter panels (`BOQParameterPanel`, structural/electrical material calculators, DC/AC BOQ calculators).
10. **Financials** — `FinancialAnalysis` (NPV, IRR, payback, etc., tied to project cost lines).
11. **AI Report** — `AIFeasibilityReport`-style outputs consuming results + BOQ data (AI credits).

**Persistence:** `AdvancedCalculatorProjectService` saves “Advanced Calculator” projects per user; dashboard lists them with status, capacity, location, financial highlights.

**Exports:** Advanced flows include **PDF-oriented reporting** (see `AdvancedPDFReport.tsx` and related generators in `src/utils/` for string, cable, ROI, production, etc., where wired to UI).

---

### 3.2 PV 3D Designer (`/pv-3d-designer`)

**Role:** **Helioscope-style** site workflow: trace footprint on **Google Maps** satellite imagery, extrude **3D building** volumes, assign roof types (flat, gable, hip, shed, pyramid per dashboard copy), per-face tilt/azimuth, and **scale-accurate module placement** in Three.js (`PV3DDesigner`, `Map3DView`, scene managers under `pv-3d-designer/threeScene/`).

**Differentiation:** Bundled inside BAESS rather than a separate GIS subscription; complements PV AI Designer Pro for users who want explicit 3D roof context without leaving the suite.

---

### 3.3 Solar Simulator (`/solar-calculator`, `/calculator`)

**Role:** Faster **feasibility / proposal-style** PV + financial modeling using `SolarCalculator` with `SolarProject`-shaped data — suitable for early-stage sizing and economics before a full Advanced Calculator build.

**Legacy persistence:** `SolarProjectsProvider` + `/project/:projectId` for stored “classic” projects.

---

### 3.4 BESS Designer (`/bess-designer`)

**Role:** Full **battery energy storage** study path.

**Sidebar sections (from navigation config in code):**

- Project Details, Location (incl. map), Daily Load Profile (preset archetypes: Residential, Commercial, Industrial, Utility-scale patterns), Design Assist, BESS Configuration, PV Sizing (disabled for pure utility-scale application mode where applicable), Cable Sizing, DG Configuration (when hybrid charging applies), Simulation Result, BOQ, Project Costing, Financial Analysis, Summary Report.

**Engineering hooks:** Hybrid and battery inverter catalogs via `inverterService`, DC cable services, `bessCalculations` utilities, charts (Recharts), PDF export (jsPDF + autotable + html2canvas patterns).

**Positioning:** 10 kWh–10 MWh narrative on marketing pages; implementation mixes representative catalogs and sizing logic for **planning-grade** studies.

---

### 3.5 AI BOQ Generator (`/boq-generator`)

**Role:** Standalone **Bill of Quantities** generation:

- **AI Assistant** tab — `BOQChat` conversational flow.
- **System Specifications** tab — `BOQForm` structured inputs.
- **BOQ Results** tab — `BOQResults` once data exists.

Useful when BOQ is needed **without** walking the entire Advanced Calculator first.

---

### 3.6 Solar AI Chat (`/solar-ai-chat`)

**Role:** Multi-session **AI chat** for structured solar tasks (`CalculationType` from `solar-calculation-prompts`), with **artifact** canvas, history sidebar, and **PDF/Excel** export utilities (`solarAIExportUtils`). Integrates with **AI credit** usage patterns like other AI surfaces.

*Note:* The dashboard card for “Solar AI Assistant” may still show “Coming Soon” in UI copy, but the **route is registered** and the page implementation exists — treat the in-app route as the source of truth for availability.

---

### 3.7 Solar Components Library (`/solar-components`)

**Role:** Browse **panels and inverters** from Supabase-backed datasets used across calculators.

**Admin-only (specific user gate in code):** Excel import (`ExcelDataImporter`), sample data controls — supports curating the component DB that powers free tools and PV AI Designer Pro.

---

### 3.8 Sandbox (`/sandbox`)

**Role:** Lab for **experimental** mini-apps (separate visual identity, model selector for AI apps).

| App | Path | Description |
|-----|------|-------------|
| Solar EDA Dashboard | `/sandbox/apps/solar-eda` | Upload **8760** hourly solar data; exploratory data analysis and charts (see `sandbox/apps/solar-eda` README in repo). |
| Solar AI Diagnostics | `/sandbox/apps/solar-ai-diagnostics` | AI diagnostics workflow with **iSolarCloud** integration hooks for O&M-style preventive maintenance narratives. |

**Settings:** `/sandbox/settings` (API setup pattern via `SandboxApiSetup` / hooks).

**Roadmap placeholders** (UI “coming soon” cards): Quick Cable Sizer, AI Document Analyzer, Quick ROI Calculator, AI Code Assistant.

---

## 4. Supporting platform features

### 4.1 Authentication & accounts

- **Supabase** auth (email + Google sign-in components exist in codebase).
- **User account** page: subscription tier display, **AI credit** remaining vs monthly limit, next reset date, transaction history.

### 4.2 Subscriptions & AI credits

- **Tiers** (from `SubscriptionPlans` / `aiCreditService`): `free`, `pro`, `advanced`, `enterprise` (enterprise contact-sales flow).
- **Checkout:** Dodo Payments integration (`subscriptionAPI.initiateCheckout` for `pro` / `advanced`).
- **Credits:** Consumed on AI-heavy actions (BOQ, reports, chat, BESS AI costing where implemented); **daily reset** logic referenced in Supabase edge function naming (`daily-credit-reset`).

### 4.3 Blog

- **Public:** Listing, search, category filters, slug-based posts (`blogService` → Supabase `blog_posts`).
- **Admin:** CRUD via `/blog/admin` and editor routes.

### 4.4 Forum

- Topic listing, slugged threads, authenticated new topic flow.

### 4.5 Reviews

- `/reviews` — user-facing reviews surface (Supabase migrations present for app reviews schema).

### 4.6 Documentation center

- `/documentation` — categorized **Getting Started**, **PV System Design**, **BOQ**, **Financial**, **Utilities**, **API & Integration** (marketing/educational structure; deep technical API docs may still evolve).

### 4.7 Integrations page (declared)

Active: **NREL PVWatts**, **Google Maps**, **OpenAI**, **Google Gemini**, **Supabase**.  
Planned / coming soon: **REST API**, **Webhooks** (as stated on `/integrations`).

### 4.8 Analytics & SEO

- **Google Analytics** (GA4) page views on route changes.
- **Helmet** meta tags; homepage SEO centralized in `src/seo/homepageSeo.ts`.
- **Sitemap** generation (`scripts/generate-sitemap.mjs`) includes homepage, tools, marketing pages, and **published** blog slugs.

---

## 5. Free tools (`/tools`)

All listed tools are **public** (no login). Many use **live Supabase component data** (panels, inverters, cables) where `supabaseData: true` in the hub metadata.

| Slug | Title (short) |
|------|----------------|
| `solar-string-sizing-calculator` | String sizing (database-backed modules/inverters) |
| `inverter-sizing-calculator` | Inverter sizing |
| `solar-cable-sizing-calculator` | DC cable sizing (IEC-oriented copy) |
| `ac-cable-sizing-calculator` | AC cable sizing (K-factor derating, IEC 60364-5-52) |
| `solar-panel-comparison` | Side-by-side panel comparison (large model count) |
| `solar-system-size-calculator` | System size from consumption |
| `solar-roi-calculator` | ROI / payback / NPV / IRR |
| `battery-storage-sizing-calculator` | BESS sizing |
| `solar-load-calculator` | Load profile / kWh / peak |
| `solar-carbon-offset-calculator` | Carbon offset |
| `solar-tilt-angle-calculator` | Tilt angle |
| `net-metering-calculator` | Net metering |
| `dc-ac-ratio-calculator` | DC/AC ratio |
| `solar-energy-production-estimator` | Production estimate |
| `voltage-drop-calculator` | Voltage drop |
| `circuit-breaker-sizing-calculator` | Breaker sizing |
| `solar-panel-area-calculator` | Panel area |
| `solar-irradiance-calculator` | Irradiance |
| `solar-financing-calculator` | Financing |
| `solar-lcoe-calculator` | LCOE |
| `inter-row-pitch-calculator` | Inter-row pitch |
| `gcr-calculator` | Ground coverage ratio |
| `annual-pr-calculator` | Annual PR |
| `dc-earthing-calculator` | DC earthing |
| `ac-earthing-calculator` | AC earthing |
| `short-circuit-calculator` | Short-circuit |
| `lightning-arrester-calculator` | Lightning arrester |

**UX standard:** Free tools follow a shared layout pattern (`ToolPageLayout`): dual-column engineering UI, PASS/WARN/FAIL compliance tables, SVG diagrams, collapsible methodology, copy/share, and **PDF report** buttons where implemented.

---

## 6. Advantages & uniqueness (fact-based)

1. **Unified web suite** — PV layout, electrical BOS thinking, BOQ, and finance live in **one** authenticated product with shared branding and navigation, reducing context switching versus using separate desktop yield + spreadsheet + CRM tools.

2. **AI at operational choke points** — BOQ generation, feasibility-style reporting, and chat calculators target the **slowest manual steps** (quantity takeoff, narrative reports, repeated what-if calculations).

3. **NREL PVWatts integration** — Yield and production pathways can align with a **widely cited** public model, aiding comparability for users familiar with U.S. NREL methodology.

4. **Large free tool surface** — Dozens of IEC-framed calculators with professional PDF outputs act as **trust builders** and acquisition funnel without forcing signup for basic engineering checks.

5. **Component scale** — Marketing and hub copy reference **thousands** of inverter/panel models in database-backed tools; this supports **real equipment** workflows vs generic placeholder specs.

6. **3D + 2D depth** — PV AI Designer Pro’s area workflow plus the dedicated **PV 3D Designer** cover both **polygonal 2D** design and **explicit 3D roof** placement.

7. **BESS co-product** — Few generalist solar web suites combine **grid-tied PV engineering** and a **multi-tab BESS** designer with economics in the same account experience.

8. **Sandbox & diagnostics** — Experimental **8760 EDA** and **SCADA-cloud-oriented** diagnostics signal a roadmap toward **data science + O&M**, beyond pure greenfield design.

---

## 7. Competitive positioning

The table below compares **typical** competitor strengths with **where BAESS fits**. Competitors are mature, well-funded, or entrenched in specific niches; BAESS should be positioned on **speed-to-first-deliverable**, **price accessibility**, **AI-assisted documentation**, and **combined PV+BESS+free tools** — not on claiming parity with every specialist depth feature on day one.

| Competitor | Typical core strength | BAESS differentiation / gap honesty |
|------------|----------------------|-----------------------------------|
| **PVsyst** | Gold-standard **hourly yield**, detailed losses, bifacial, shading scenes, bankable report culture (desktop). | BAESS is **web-first** and workflow-broad; PVsyst remains deeper for **certification-grade hourly simulation** purists. BAESS wins on **collaboration**, **AI BOQ/reporting**, and **zero install** for many workflows. |
| **Helioscope** | **3D shade** on aerial imagery, commercial workflow, fleet-scale. | BAESS **PV 3D Designer** echoes that **map → 3D roof → modules** pattern **inside** a wider suite (single vendor context). Helioscope still leads where enterprise **fleet / CRM** integrations are mandatory. |
| **Aurora Solar** | **Sales** engineering, LIDAR/shade, CRM, proposal automation at enterprise price points. | BAESS targets **engineer-first** detailed tabs (DC/AC, BOQ) and **free calculators** for top-of-funnel; not a full **Aurora-style** sales OS. |
| **PVcase** | **Autodesk Revit / CAD** deep integration, construction-ready layouts for EPC BIM processes. | BAESS does **not** replace Revit-native BIM; it competes on **browser accessibility**, rapid BOQ, and **non-CAD** users. PVcase wins for **BIM-centric** EPCs. |
| **Rated Power** | **Utility-scale** development: layouts, GTM, granular project finance at project gigawatt scale. | BAESS spans **residential to large commercial** narratives and **BESS**; Rated Power wins for **full utility development platform** depth and enterprise procurement workflows. |

**Summary sentence for GTM:**  
*BAESS Labs is an AI-augmented, web-based solar engineering and BOQ suite that unifies PV design, 3D site layout, BESS planning, and financials—trading the last 5% of specialist-desktop depth for 10× faster collateral production on mid-complexity projects.*

---

## 8. Target users

- **EPC / design engineers** who need BOQ + electrical sizing + yield in one session.
- **Developers / PMs** doing early feasibility before outsourcing detailed yield to specialist tools.
- **BESS integrators** exploring sizes, costs, and finance alongside PV.
- **Students & installers** using **free tools** for code-adjacent checks and learning.

---

## 9. Known implementation notes (for internal alignment)

- **Products page** lists AI BOQ with link target `/pv-designer`; the routed **3D designer** path in `App.tsx` is `/pv-3d-designer`. Marketing links should be checked for consistency.
- **Dashboard** “Solar AI Assistant” card copy vs live `/solar-ai-chat` route — align messaging to avoid user confusion.
- **Admin email** hard-coded in places (`Dashboard`, `SolarComponentsPage`) — environment-driven config would be safer for forks.

---

## 10. Document control

| Field | Value |
|-------|--------|
| Title | BAESS Labs Platform Documentation |
| Scope | Application features & routes from repository analysis |
| Maintainer | Product / engineering team |

---

*End of document.*
