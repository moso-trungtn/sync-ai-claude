---
name: Project Architecture - Service Modules
description: 5 service modules that make up the project architecture
type: project
---

## 5 Service Modules

The MOSO project consists of 5 Maven-based Java service modules:

### 1. **@base/** (v3.55.0-SNAPSHOT)
- **Role:** Foundation infrastructure and parent POM
- **Technology:** Java 17, Maven, GWT 2.11.0, Google Cloud APIs
- **Purpose:** Provides dependency management, build templates, core utilities
- **Key Packages:** com.moso.*, com.mvu.*, com.google.*

### 2. **@moso/** (v3.55.0-SNAPSHOT, WAR)
- **Role:** Main web application for loan origination
- **Technology:** GWT frontend + Java backend
- **Contains:** AppServer.java (entry point), AppCronConfig.java (100+ cron jobs)
- **Depends on:** packs/loan, packs/billing, packs/hr, moso-pricing
- **Features:** Loan management, user operations, background job orchestration

### 3. **@moso-pricing/** (v3.19.0-SNAPSHOT, WAR/JAR)
- **Role:** Microservice for rate parsing and pricing calculations
- **Key Services:** ComputeAdjustmentOp, QuoteServer, LenderParser, RateSheetEmailHandler
- **Depends on:** packs/quote, Google Cloud Datastore
- **Features:** Ratesheet parsing, rate calculations, adjustments, quote calculations
- **Can be:** Deployed independently (jar-packaging profile)

### 4. **@moso-configuration/** (v3.0.0-SNAPSHOT, JAR)
- **Role:** Configuration and template management
- **Contains:** JSON/HTML templates, configuration backups
- **Depends on:** packs/loan (for entity definitions)
- **Features:** System templates, email templates, UI templates

### 5. **@packs/** (v3.55.0-SNAPSHOT, POM aggregator)
- **Role:** Collection of reusable domain-specific business logic packs
- **Submodules:**
  - **loan** - Loan origination & management core
  - **quote** - Quote & rate structures
  - **billing** - Payment & invoicing
  - **hr** - HR & recruiting
  - **google-apis** - Google integration
  - **ringcentral-apis** - RingCentral integration
  - **pdfbox** - PDF processing
  - **appengine-awt** - AWT for App Engine
  - **reso-webapi-client** - RESO WebAPI

## Key Architecture Points

- **Pattern:** Operation pattern (extends AppEngineOp, execute() method with JSON)
- **Frontend:** GWT 2.11.0 compiles to JavaScript
- **Database:** Google Cloud Datastore
- **Cloud Platform:** Google App Engine
- **Email:** SendGrid/Mailgun
- **Communication:** Twilio, RingCentral

## Documentation Created

- `PROJECT_ARCHITECTURE.md` - Complete technical architecture guide
- `QUICK_REFERENCE.md` - Quick lookup card
- `MODULE_INTERACTIONS.md` - Data flows and communication patterns
