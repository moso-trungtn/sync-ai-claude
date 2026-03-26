# UNDERSTAND MOSO - COMPLETE CODEBASE REFERENCE

**Last Updated:** 2026-03-17
**Project Versions:** base 3.55.0-SNAPSHOT | moso 3.55.0-SNAPSHOT | moso-pricing 3.19.0-SNAPSHOT | moso-configuration 3.0.0-SNAPSHOT | packs 3.55.0-SNAPSHOT

---

## 📋 TABLE OF CONTENTS

1. [Project Overview](#project-overview)
2. [5 Core Modules](#5-core-modules)
3. [Directory Structure](#directory-structure)
4. [Technical Stack](#technical-stack)
5. [Module Dependencies](#module-dependencies)
6. [Code Organization Patterns](#code-organization-patterns)
7. [Runtime Data Flow](#runtime-data-flow)
8. [Module Communication](#module-communication)
9. [Key Files & Entry Points](#key-files--entry-points)
10. [Quick Code Location Guide](#quick-code-location-guide)
11. [Build Sequence](#build-sequence)
12. [Common Development Tasks](#common-development-tasks)

---

## PROJECT OVERVIEW

**MOSO** is a comprehensive **Mortgage Origination System** built on Java 17 with Google Cloud Platform. It's an enterprise web application for managing the complete loan origination lifecycle, from quote to closing.

**Core Purpose:**
- Complete mortgage loan origination platform
- Rate/pricing calculation engine (ComputeAdjustmentOp, QuoteServer)
- Billing and payment processing
- Document management and compliance
- HR and recruiting integration
- Multi-lender rate management

**Architecture Style:** Modular monolith with microservice-ready design (moso-pricing can be deployed independently)

---

## 5 CORE MODULES

### 1️⃣ **base/** - Foundation & Parent POM
- **Responsibility:** Root dependency management and build infrastructure
- **Version:** 3.55.0-SNAPSHOT
- **Location:** `/Users/trungthach/IdeaProjects/base/`
- **Packaging:** POM (aggregator)

**Sub-modules:**
- `base/pom.xml` - Root POM with all dependency versions
- `base/core/` - Core utilities and shared code
- `base/module/` - Module parent POM
- `base/product/` - Product parent POM
- `base/appengine/` - Google App Engine configuration
- `base/configuration/` - Shared configuration

**Key Dependencies Defined:**
- Java 17
- GWT 2.11.0 (frontend)
- Google Cloud (Datastore 2.18.4, Storage, Tasks, Pub/Sub)
- Google APIs (Drive, Calendar, Directory, OAuth2)
- SendGrid, Mailgun, Twilio, RingCentral
- Apache POI (Excel), PDFBox (PDF)
- OkHttp 4.8.1 (HTTP client)
- JJWT 0.12.3 (JWT/authentication)
- JUnit 5.2.0 (testing)
- Bouncy Castle (cryptography)

---

### 2️⃣ **moso/** - Main Web Application
- **Responsibility:** User interface, loan operations, background jobs
- **Version:** 3.55.0-SNAPSHOT
- **Location:** `/Users/trungthach/IdeaProjects/moso/`
- **Packaging:** WAR (Web Application Archive)
- **Technology:** GWT 2.11.0 + Java backend

**Key Files:**
```
moso/src/main/java/com/lenderrate/
├── AppServer.java              ⭐ Main entry point - initializes modules
├── AppCronConfig.java          ⭐ 100+ scheduled background jobs
├── client/                     (GWT frontend - 13+ directories)
│   ├── view/
│   ├── view/marketing/
│   └── [other UI components]
├── server/                     (Backend services)
│   ├── op/                     (60+ operation classes)
│   │   ├── user/               (User operations)
│   │   ├── followup/           (Follow-up logic)
│   │   ├── desk/               (Desk operations)
│   │   ├── cron/               (100+ scheduled job implementations)
│   │   └── [other operations]
│   ├── auth/                   (Authentication)
│   └── [Mail handlers]
└── shared/                     (Shared client/server code)
```

**Core Responsibilities:**
- GWT frontend compilation to JavaScript
- Loan lifecycle management (create, process, close)
- User management and authentication
- Desk and team operations
- Commission calculations
- Escalation management
- Third-party integrations (Zoom, Google Drive, Twilio, RingCentral)
- Mail handler integration (announcements, escalations, leads)
- Database synchronization
- License expiration alerts
- Performance tracking

**Main Dependencies:**
- `packs/loan` - Core loan operations
- `packs/billing` - Payment processing
- `packs/hr` - HR operations
- `moso-pricing` (test scope) - Rate calculations
- OkHttp 4.8.1
- JJWT 0.12.3
- QRGen 1.4 (QR codes)

---

### 3️⃣ **moso-pricing/** - Pricing & Rate Microservice
- **Responsibility:** Rate sheet parsing, quote calculations, pricing engine
- **Version:** 3.19.0-SNAPSHOT
- **Location:** `/Users/trungthach/IdeaProjects/moso-pricing/`
- **Packaging:** WAR (default) or JAR (with `-Pjar-packaging` profile)
- **Can be deployed independently**

**Key Files:**
```
moso-pricing/src/main/java/com/mosopricing/
├── RateSheetEmailHandler.java      ⭐ Email ratesheet processing
├── LenderMailHandler.java
├── server/
│   ├── op/                         (Operational classes)
│   │   ├── RateOps.java
│   │   ├── GetAvailableRateModes.java
│   │   ├── LenderRateLoader.java   ⭐ Parse ratesheets
│   │   ├── ComputeAdjustmentOp.java ⭐ Calculate adjustments (KEY SERVICE)
│   │   ├── RunPricingOp.java
│   │   ├── RunNonQMPricingOp.java
│   │   ├── rate/
│   │   │   ├── Product.java
│   │   │   └── NonQMProduct.java
│   │   ├── parser/
│   │   │   ├── LenderParser.java
│   │   │   ├── NonQMLenderParser.java
│   │   │   ├── LenderParserMap.java
│   │   │   ├── rate/
│   │   │   ├── adjustment/
│   │   │   └── calculator/
│   │   ├── FindLendersForState.java
│   │   ├── QuotableLendersInfoOp.java
│   │   ├── RerunPricingOp.java
│   │   ├── UploadRateSheet.java
│   │   ├── ProcessBrokerEmail.java
│   │   └── CreateCronJobParserBuild.java
│   └── parser/
│       ├── calculator/
│       │   ├── QuoteServer.java           ⭐ QM calculations (KEY SERVICE)
│       │   ├── NonQMQuoteServer.java
│       │   ├── ModeResolver.java          ⭐ Rate mode resolution
│       │   ├── LenderDataProvider.java
│       │   ├── QuoteDataProvider.java
│       │   └── [calculator groups]
│       └── LenderParserMap.java
├── docs/                           (Comprehensive documentation)
│   ├── rate-parser.md
│   ├── adj-tableinfo.md
│   ├── adj-pageparser.md
│   ├── adj-conditions.md
│   ├── adj-calculator.md
│   ├── adj-howto-new-parser.md
│   ├── excel-parser-tricks.md
│   ├── parser-patterns.md
│   ├── ratesheet-update-process.md
│   ├── update-lender-doc.md
│   ├── lenders/                    (Lender-specific documentation)
│   └── MEMORY.md
├── CLAUDE.md                       (AI agent instructions)
└── shared/
    ├── entity/
    │   └── Redirection.java
    └── typekey/
        └── [rate/loan type keys]
```

**Key Services:**

**ComputeAdjustmentOp** ⭐ PRIMARY PRICING SERVICE
- Entry point for all rate calculations
- Handles both QM (Qualified Mortgage) and NonQM loans
- Takes quote parameters (amount, rate, adjustments, etc.)
- Returns calculated adjustments and final rate
- Called by: moso when user requests a quote

**QuoteServer** ⭐ CALCULATION ENGINE
- Core QM quote calculation logic
- Rate mode resolution
- Lender data integration
- Adjustment application
- Factory method pattern for rate calculations

**ModeResolver** ⭐ CRITICAL FOR CORRECTNESS
- Bridges quote parameters to rate modes
- Handles loan type, purpose, channel mapping
- Essential for correct rate lookups

**LenderRateLoader** ⭐ RATESHEET PARSING
- Parses Excel/PDF ratesheets from lenders
- Extracts rates, adjustments, conditions
- Stores results in Google Cloud Datastore
- Lender-specific parsing logic

**RateSheetEmailHandler** ⭐ EVENT-DRIVEN
- Processes incoming lender emails with attachments
- Extracts attachment paths
- Triggers parsing and validation
- Email-based upload mechanism

**Core Responsibilities:**
- Parse lender rate sheets (Excel/PDF)
- Extract rates and adjustment tables
- Calculate quote adjustments for various loan products
- Handle QM and NonQM pricing rules
- Manage rate mode resolution
- Provide data persistence
- Support email-based ratesheet uploads
- Resolve rate conditions

**Main Dependencies:**
- `packs/quote` (3.55.0-SNAPSHOT) - Quote entities and structures
- Google Cloud Datastore 2.18.4 - Data persistence
- OkHttp 4.8.1 - HTTP client
- Apache POI - Excel processing
- PDFBox - PDF processing
- Bouncy Castle - Cryptography

**Documentation:**
- `docs/rate-parser.md` - Rate extraction architecture
- `docs/adj-tableinfo.md` - Adjustment table structure
- `docs/adj-pageparser.md` - Page parsing strategies
- `docs/adj-conditions.md` - Condition resolution
- `docs/adj-calculator.md` - Calculation logic
- `docs/adj-howto-new-parser.md` - Complete guide for new parsers
- `docs/lenders/` - Lender-specific documentation

---

### 4️⃣ **moso-configuration/** - Configuration & Templates
- **Responsibility:** System templates and configuration storage
- **Version:** 3.0.0-SNAPSHOT
- **Location:** `/Users/trungthach/IdeaProjects/moso-configuration/`
- **Packaging:** JAR
- **Minimal codebase** - primarily resources

**Contains:**
- Database backup configurations
- JSON templates:
  - Rate quote templates
  - Themed templates (metallic, header styles)
  - Loan-specific templates (VA, construction, LOLOA, bridge loans, etc.)
  - Email templates
  - Blog and campaign templates
  - Loan campaign configurations

**Dependencies:**
- `packs/loan` (3.55.0-SNAPSHOT)

**Key Responsibilities:**
- System template storage
- Configuration persistence
- Version control of settings
- UI template management

---

### 5️⃣ **packs/** - Reusable Business Logic Packs
- **Responsibility:** Domain-specific, pluggable business logic modules
- **Version:** 3.55.0-SNAPSHOT (most packs)
- **Location:** `/Users/trungthach/IdeaProjects/packs/`
- **Packaging:** POM (aggregator with 9 submodules)

**Each pack structure:**
```
pack-name/
├── src/main/java/com/mvu/[packname]/
│   ├── client/          (GWT frontend views)
│   ├── server/
│   │   ├── op/          (Operation classes)
│   │   └── [logic]
│   └── shared/
│       ├── entity/      (Data entities)
│       ├── typekey/     (Type keys/enums)
│       └── [shared code]
├── src/test/java/       (Unit tests)
└── pom.xml
```

#### **A. packs/loan** - Core Loan Origination
- Loan entity lifecycle (create, update, close)
- Client/borrower information management
- Branch and company management
- Lender partnership management
- License management and tracking
- Document handling and compliance
- Commission calculations
- Discount eligibility
- Escalation management
- 100+ cron jobs for monitoring and notifications

**Key Entities:** Loan, Client, Company, Branch, Lender, LenderUser, LenderAgreement, License, Admin, Escrow, ESignatureStyle, and 450+ other entities

**Mail Handlers:**
- LenderMailHandler - Lender communications
- EscrowMailHandler - Escrow processing
- Lead automation email parsing

**Location:** `/packs/loan/src/main/java/com/mvu/loan/`

#### **B. packs/quote** - Quote & Rate Management
- Quote entity operations
- Rate structures and rate modes
- Adjustment definitions (points, fees)
- Lender information
- Quote configuration and operations

**Key Entities:** Quote, Rate, Adjustment, Lender, RateMode, LoanType, LoanChannel, PurposeType, LenderType

**Type Keys:**
- RateMode: fixed, ARM, 7/1 ARM, 5/1 ARM, etc.
- LoanType: Conventional, FHA, VA, USDA, NonQM
- LoanChannel: Broker, Retail, Correspondent
- PurposeType: Purchase, Refinance, CashOut, LoanModification

**Location:** `/packs/quote/src/main/java/com/mvu/quote/`

#### **C. packs/billing** - Billing & Payment Processing
- Invoice generation
- Payment tracking
- Auto-charging configuration
- Transaction processing
- Billing automation (cron jobs)

**Key Entities:** BillingStatus, BillingPlanHistory, BillingTransaction

**Location:** `/packs/billing/src/main/java/com/mvu/billing/`

#### **D. packs/hr** - Human Resources
- HR section management
- Recruiting module features
- Out-of-office notifications
- HR permissions and access control

**Location:** `/packs/hr/src/main/java/com/ato/hr/`

#### **E. packs/google-apis** - Google Integration
- Google Drive API integration
- Google Calendar API integration
- Google Directory API integration
- Google OAuth2 authentication
- Google Cloud Storage integration
- Google Cloud Datastore integration

**Location:** `/packs/google-apis/src/main/java/com/mvu/gapi/`

#### **F. packs/ringcentral-apis** - RingCentral Integration
- Call recording synchronization
- SMS log management
- Extension information retrieval
- Call log operations

**Location:** `/packs/ringcentral-apis/src/main/java/com/moso/ringcentral/`

#### **G. packs/pdfbox** - PDF Processing
- PDF document manipulation
- PDF utility functions

#### **H. packs/appengine-awt** - AWT Support
- AWT support for App Engine deployment

#### **I. packs/reso-webapi-client** - RESO Integration
- RESO WebAPI client for real estate industry data

---

## DIRECTORY STRUCTURE

```
/Users/trungthach/IdeaProjects/
│
├── base/                                    (Foundation)
│   ├── pom.xml                             (Root POM - dependency management)
│   ├── core/                               (Core utilities)
│   ├── module/                             (Module parent POM)
│   ├── product/                            (Product parent POM)
│   ├── appengine/                          (App Engine configuration)
│   ├── configuration/                      (Shared configuration)
│   ├── xyz/                                (Other utilities)
│   ├── CDN/                                (CDN resources)
│   ├── hooks/                              (Git hooks)
│   ├── scripts/                            (Build scripts)
│   └── tools/                              (Development tools)
│
├── moso/                                   (Main Application - WAR)
│   ├── pom.xml                            (moso dependencies)
│   ├── src/main/java/com/lenderrate/
│   │   ├── AppServer.java                 (⭐ Main entry point)
│   │   ├── AppCronConfig.java             (⭐ Job scheduling)
│   │   ├── client/                        (GWT frontend)
│   │   ├── server/                        (Backend services)
│   │   │   ├── op/                        (Operation classes)
│   │   │   ├── auth/                      (Authentication)
│   │   │   └── [Mail handlers]
│   │   └── shared/                        (Shared code)
│   ├── src/test/java/                     (Unit tests)
│   └── src/main/resources/                (Configuration)
│
├── moso-pricing/                           (Pricing Microservice - WAR/JAR)
│   ├── pom.xml
│   ├── src/main/java/com/mosopricing/
│   │   ├── RateSheetEmailHandler.java     (⭐ Email handler)
│   │   ├── server/
│   │   │   ├── op/
│   │   │   │   ├── ComputeAdjustmentOp.java  (⭐ Pricing service)
│   │   │   │   ├── LenderRateLoader.java     (⭐ Ratesheet parsing)
│   │   │   │   └── [other operations]
│   │   │   └── parser/
│   │   │       ├── calculator/
│   │   │       │   ├── QuoteServer.java      (⭐ Calculation engine)
│   │   │       │   ├── ModeResolver.java     (⭐ Rate mode resolution)
│   │   │       │   └── [calculator groups]
│   │   │       └── [parser classes]
│   │   └── shared/
│   ├── docs/                               (📚 Comprehensive documentation)
│   │   ├── rate-parser.md
│   │   ├── adj-tableinfo.md
│   │   ├── adj-pageparser.md
│   │   ├── adj-conditions.md
│   │   ├── adj-calculator.md
│   │   ├── adj-howto-new-parser.md
│   │   ├── excel-parser-tricks.md
│   │   ├── parser-patterns.md
│   │   ├── ratesheet-update-process.md
│   │   ├── lenders/                     (Lender-specific docs)
│   │   └── MEMORY.md
│   ├── CLAUDE.md                         (AI agent instructions)
│   └── src/test/java/                    (Unit tests)
│
├── moso-configuration/                   (Configuration - JAR)
│   ├── pom.xml
│   └── src/main/resources/               (Templates & configs)
│
├── packs/                                 (Business Logic Packs - POM aggregator)
│   ├── pom.xml                           (Packs parent POM)
│   │
│   ├── loan/                             (Loan Origination)
│   │   ├── src/main/java/com/mvu/loan/
│   │   │   ├── server/op/               (60+ loan operations)
│   │   │   ├── shared/entity/           (450+ entities)
│   │   │   └── [other packages]
│   │   ├── src/test/java/               (Unit tests)
│   │   ├── pom.xml
│   │   └── CLAUDE.md
│   │
│   ├── quote/                            (Quote Management)
│   │   ├── src/main/java/com/mvu/quote/
│   │   │   ├── shared/entity/           (Quote entities)
│   │   │   ├── shared/typekey/          (Type keys)
│   │   │   └── [operations]
│   │   └── pom.xml
│   │
│   ├── billing/                          (Billing & Payment)
│   │   ├── src/main/java/com/mvu/billing/
│   │   └── pom.xml
│   │
│   ├── hr/                               (HR & Recruiting)
│   │   ├── src/main/java/com/ato/hr/
│   │   └── pom.xml
│   │
│   ├── google-apis/                      (Google Integration)
│   │   └── pom.xml
│   │
│   ├── ringcentral-apis/                 (RingCentral Integration)
│   │   └── pom.xml
│   │
│   ├── pdfbox/                           (PDF Processing)
│   │   └── pom.xml
│   │
│   ├── appengine-awt/                    (AWT Support)
│   │   └── pom.xml
│   │
│   └── reso-webapi-client/               (RESO Integration)
│       └── pom.xml
│
├── PROJECT_ARCHITECTURE.md              (📚 Detailed architecture)
├── MODULE_INTERACTIONS.md                (📚 Data flows & interactions)
├── QUICK_REFERENCE.md                   (📚 Quick lookup card)
└── UNDERSTAND_MOSO.md                   (📚 THIS FILE - Complete reference)
```

---

## TECHNICAL STACK

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| **Language** | Java | 17 | Strong typing, modern features |
| **Build** | Maven | Multi-module | base → packs → moso-pricing → moso |
| **Frontend** | GWT | 2.11.0 | Compiles to JavaScript, type-safe |
| **Backend Framework** | Custom Operation Pattern | - | Consistent request/response handling |
| **Web Services** | JAX-WS/JAXB | - | SOAP services |
| **Cloud Platform** | Google App Engine | - | Serverless deployment |
| **Database** | Google Cloud Datastore | 2.18.4 | NoSQL/Key-value store |
| **Cloud Services** | Cloud Storage, Tasks, Pub/Sub | - | Infrastructure services |
| **Email Service** | SendGrid, Mailgun | - | Transactional email |
| **Communication** | Twilio, RingCentral | - | SMS, voice, call recording |
| **Data Processing** | Apache POI | - | Excel file parsing |
| **PDF Processing** | PDFBox | - | PDF manipulation |
| **HTTP Client** | OkHttp | 4.8.1 | HTTP requests |
| **Authentication** | JWT/TOTP | JJWT 0.12.3 | Secure token handling |
| **Security** | Bouncy Castle, Jasypt | - | Cryptography and encryption |
| **Testing** | JUnit 5 | 5.2.0 | Unit and integration tests |
| **Utilities** | Google Guava | 31.1-jre | Collections and helpers |

---

## MODULE DEPENDENCIES

### Dependency Graph

```
                      base/pom.xml (v3.55.0)
                         [Root POM]
                              ↓
         _____________________┴_______________________
        |                     |                      |
    base/core         base/appengine          base/module
        ↓                     ↓                      ↓
        └─────────────────────┼──────────────────────┘
                              ↓
                   base/product/pom.xml
                              ↓
          ________________________|_________________________
         |                       |                       |
     moso (WAR)        moso-pricing (WAR/JAR)    moso-configuration (JAR)
   v3.55.0              v3.19.0                    v3.0.0
         |                       |                       |
    _____↓_____            ______|                       |
   |     |     |     |     |      |                      |
packs: loan, billing, hr, quote  |                      |
(all v3.55.0)                    |                      |
                                 |                      |
    ┌────────────────────────────┘            ┌────────┘
    |                                         |
    └── packs/quote                      depends on
        (Quote entities)                  packs/loan
```

### Dependency Rules

**moso depends on:**
- ✓ `packs/loan` - Core loan operations
- ✓ `packs/billing` - Payment processing
- ✓ `packs/hr` - HR operations
- ✓ `moso-pricing` (test scope) - Pricing calculations

**moso-pricing depends on:**
- ✓ `packs/quote` - Quote entities and structures
- ✓ Google Cloud Datastore - Data persistence

**moso-configuration depends on:**
- ✓ `packs/loan` - Loan entities for templates

**packs/loan depends on:**
- ✓ `packs/quote` - For rate locks and pricing
- ✓ `base/module` or `base/product` - Infrastructure

**All packs depend on:**
- ✓ `base/module` or `base/product` - Parent POM

**All modules depend on:**
- ✓ `base/pom.xml` - Dependency management

### Build Order (Correct Sequence)

```bash
1. base/            → mvn clean install
2. packs/           → mvn clean install
3. moso-pricing/    → mvn clean install
4. moso-config/     → mvn clean install
5. moso/            → mvn clean install
```

---

## CODE ORGANIZATION PATTERNS

### 1. **Operation Pattern** (Ubiquitous)

All business logic follows the Operation pattern:

```java
public class MyOp extends AppEngineOp {
    public String execute(String jsonParams) {
        // 1. Parse JSON parameters
        Map<String, Object> params = JSON.parse(jsonParams);

        // 2. Execute business logic
        Object result = doBusinessLogic(params);

        // 3. Return JSON response
        return JSON.stringify(result);
    }
}
```

**Used everywhere:**
- moso operations (60+)
- moso-pricing operations (rate calculations)
- packs/loan operations
- packs/quote operations
- packs/billing operations
- Email handlers
- Cron jobs

**Benefits:**
- Consistent request/response handling
- Easy to test
- Simple serialization/deserialization
- Clear contract between caller and callee

---

### 2. **Module Structure Pattern**

Each module/pack follows consistent organization:

```
[module]/
├── pom.xml                        (Dependencies for this module)
├── src/main/java/
│   ├── client/                    (GWT frontend - compiled to JavaScript)
│   │   ├── view/                  (UI views and pages)
│   │   ├── [SectionName]Mod.java  (Module configuration)
│   │   └── [other UI classes]
│   ├── server/
│   │   ├── op/                    (Operation classes)
│   │   │   ├── [Entity]Ops.java   (CRUD operations)
│   │   │   ├── [Custom]Op.java    (Custom logic)
│   │   │   └── [other operations]
│   │   └── [utility classes]
│   └── shared/
│       ├── entity/                (Data entities - @Bean annotated)
│       ├── typekey/               (Enums and type constants)
│       └── [shared interfaces]
├── src/test/java/
│   └── [Test classes]
└── src/main/resources/
    ├── [SectionName].gwt.xml      (GWT module configuration)
    └── [other resources]
```

---

### 3. **GWT Architecture**

**Client Code** (Runs in browser as JavaScript):
```
client/view/*.java → Compiled to JavaScript
```

**Shared Code** (Compiled to both JavaScript and Java):
```
shared/entity/*.java → Entities used by client and server
shared/typekey/*.java → Constants and enums
```

**Server Code** (Runs on App Engine):
```
server/op/*.java → Business logic operations
server/*.java → Utility and processing classes
```

**Benefits:**
- Strong typing across client-server boundary
- Single language (Java) for full stack
- Type-safe communication
- Rich, responsive UI

---

### 4. **Cron-Based Automation**

Extensive background job infrastructure:

```
AppCronConfig.java (moso)
├── 100+ scheduled jobs
├── Daily monitoring
├── Weekly reports
├── Monthly accounting
└── [Custom intervals]

Each job:
├── Extends AppEngineOp
├── Scheduled via Cloud Tasks
└── Logs results to database
```

**Job Types:**
- Loan status monitoring
- License expiration alerts
- Email notifications
- Database synchronization
- Commission calculations
- Account verification
- ACH payment processing
- Performance tracking

---

### 5. **Email-Driven Processing**

Event-driven architecture via email:

```
External Email
    ↓
MailHandler (routes based on sender/subject)
    ↓
Specific Processor (domain-specific logic)
    ↓
Database Update
    ↓
Notification/UI Update
```

**Email Handlers:**
- RateSheetEmailHandler (moso-pricing) - Lender rate uploads
- LenderMailHandler (packs/loan) - Lender communications
- EscrowMailHandler (packs/loan) - Escrow processing
- LeadPopMailProcessor (packs/loan) - Lead automation
- RecruitingMailProcessor (packs/hr) - Recruiting events
- AnnouncementMailHandler (moso) - System announcements

---

### 6. **Entity Organization**

Entities are organized by package and use `@Bean` annotation:

```
shared/entity/
├── Core entities: Loan, Client, Company, Branch
├── Quote entities: Quote, Rate, Adjustment
├── Billing entities: BillingStatus, BillingTransaction
├── External: GoogleDriveConfig, RingCentralExtension
└── [450+ total entities in loan pack]
```

Each entity:
- Has fields with @Field annotations
- Is annotated with @Bean
- Has getter/setter methods
- Can be persisted to Datastore
- Is serializable to JSON

---

## RUNTIME DATA FLOW

### Flow 1: User Submits Quote Request

```
1. User (Browser)
   └─ Fills quote form (amount, rate, loan type, etc.)

2. moso Frontend (GWT JavaScript)
   └─ Sends quote parameters to backend

3. moso AppServer (Operation Pattern)
   └─ Receives parameters, calls ComputeAdjustmentOp

4. moso-pricing ComputeAdjustmentOp
   └─ Validates parameters
   └─ Calls QuoteServer.calculate()

5. moso-pricing QuoteServer
   └─ Loads lender data from Datastore
   └─ Resolves rate mode via ModeResolver
   └─ Applies adjustments
   └─ Calculates final rate

6. Google Cloud Datastore
   └─ Provides cached lender rates/adjustments

7. moso-pricing Returns
   └─ Adjustment values, final rate, points, fees

8. moso Frontend
   └─ Displays quote result to user
```

**Time:** ~200-500ms (depends on Datastore latency)

---

### Flow 2: Lender Sends Rate Sheet Update

```
1. External Lender
   └─ Sends email with Excel/PDF ratesheet attachment

2. SendGrid/Mailgun Email Gateway
   └─ Routes to moso-pricing webhook

3. RateSheetEmailHandler (moso-pricing)
   └─ Receives email
   └─ Extracts attachment
   └─ Identifies lender by sender

4. LenderRateLoader (moso-pricing)
   └─ Looks up LenderParserMap
   └─ Gets lender-specific parser
   └─ Parses Excel/PDF:
      ├─ Extract rates by product
      ├─ Extract adjustments
      └─ Extract conditions

5. Validation
   └─ Check data integrity
   └─ Verify rates are reasonable

6. Google Cloud Datastore
   └─ Stores parsed rates
   └─ Updates cache

7. System Notification
   └─ Sends confirmation to lender
   └─ Notifies admins of update

8. Next Quote Request
   └─ Uses updated rates
```

**Result:** Updated rates available within seconds

---

### Flow 3: Background Job Execution

```
1. Google Cloud Tasks
   └─ Triggers at scheduled time (2:00 AM, daily, etc.)

2. moso AppCronConfig
   └─ Routes to specific job (e.g., DailyLoanStatusJob)

3. Cron Job Operation (AppEngineOp)
   └─ Execute business logic:
      ├─ Query loans with filters
      ├─ Check status conditions
      ├─ Calculate fees/commissions
      └─ Generate notifications

4. Data Updates
   └─ Update loan records in Datastore
   └─ Create billing transactions
   └─ Update performance metrics

5. Notifications
   └─ Send emails via SendGrid
   └─ Send SMS via Twilio
   └─ Update dashboard alerts

6. Logging
   └─ Record job execution
   └─ Log any errors
```

**Frequency:** Daily, weekly, monthly (100+ jobs configured)

---

## MODULE COMMUNICATION

### Pattern 1: Direct Operation Calls

**Caller** → `Operation.execute(jsonParams)` → **Callee Operation**

```
moso → packs/loan LoanOps
moso → moso-pricing ComputeAdjustmentOp
moso-pricing → packs/quote QuoteOps
packs/loan → packs/billing BillingOps
```

---

### Pattern 2: Shared Entity Model

**Data structures shared between modules:**

```
packs/quote/shared/entity/
├── Quote.java        ← Used by moso, moso-pricing, packs/loan
├── Rate.java         ← Used by moso-pricing, packs/quote
├── Adjustment.java   ← Used by moso-pricing, packs/quote
└── Lender.java       ← Used by packs/loan, moso-pricing
```

**Entity Flow:**
- moso creates Quote entity
- moso-pricing reads Quote, calculates adjustments
- moso reads updated Quote with calculation results
- Entities serialized to JSON for transport

---

### Pattern 3: Email-Driven Events

**Email received** → **MailHandler** → **Parse** → **Database** → **UI Update**

```
RateSheetEmailHandler → LenderRateLoader → Datastore → moso UI
LenderMailHandler → EmailProcessor → Datastore → Loan management
```

---

### Pattern 4: External Service Integration

```
moso operations
├─→ Google Cloud Datastore (persistence)
├─→ Google Cloud Storage (documents)
├─→ Google Cloud Tasks (scheduling)
├─→ Google APIs (Drive, Calendar, Directory)
├─→ SendGrid (email)
├─→ Twilio (SMS)
├─→ RingCentral (calls/recordings)
└─→ RESO WebAPI (industry data)

moso-pricing operations
├─→ Google Cloud Datastore (rates, adjustments)
├─→ Email handlers (rate uploads)
└─→ Rate calculation services
```

---

## KEY FILES & ENTRY POINTS

### moso (Main Application)

| File | Location | Purpose |
|------|----------|---------|
| **AppServer.java** | `moso/src/main/java/com/lenderrate/` | ⭐ Main entry point, initializes all modules |
| **AppCronConfig.java** | `moso/src/main/java/com/lenderrate/` | ⭐ 100+ scheduled jobs configuration |
| **MOSOTypeWatchers.java** | `moso/src/main/java/com/lenderrate/server/` | Type system watchers |
| **VerifyUserOp.java** | `moso/src/main/java/com/lenderrate/server/op/user/` | User verification logic |
| **FindRecentSearchHistoriesOp.java** | `moso/src/main/java/com/lenderrate/server/op/` | Search history operations |

### moso-pricing (Pricing Service)

| File | Location | Purpose |
|------|----------|---------|
| **ComputeAdjustmentOp.java** | `moso-pricing/server/op/` | ⭐ PRIMARY PRICING SERVICE - Rate adjustment calculations |
| **QuoteServer.java** | `moso-pricing/server/parser/calculator/` | ⭐ Core quote calculation engine for QM loans |
| **NonQMQuoteServer.java** | `moso-pricing/server/parser/calculator/` | Quote calculations for NonQM loans |
| **ModeResolver.java** | `moso-pricing/server/parser/calculator/` | ⭐ Rate mode resolution - bridges parameters to rates |
| **LenderRateLoader.java** | `moso-pricing/server/op/` | ⭐ Ratesheet parsing and loading |
| **RateSheetEmailHandler.java** | `moso-pricing/` | ⭐ Email handler for lender ratesheet uploads |
| **LenderParserMap.java** | `moso-pricing/server/parser/` | Registry of lender-specific parsers |
| **LenderParser.java** | `moso-pricing/server/op/parser/` | Base parser for lender ratesheets |
| **LenderMailHandler.java** | `moso-pricing/` | Email handler for lender communications |

### packs/loan (Loan Origination)

| File | Location | Purpose |
|------|----------|---------|
| **LoanOps.java** | `packs/loan/server/op/` | ⭐ Core loan operations (CRUD, lifecycle) |
| **LoanServer.java** | `packs/loan/server/` | Loan business logic server |
| **AnnouncementMailHandler.java** | `packs/loan/server/` | Email handler for announcements |
| **EscrowMailHandler.java** | `packs/loan/server/` | Email handler for escrow processing |
| **LeadPopMailProcessor.java** | `packs/loan/server/parser/` | Lead automation email processing |
| **Loan.java** | `packs/loan/shared/entity/` | Loan entity (main entity) |
| **Client.java** | `packs/loan/shared/entity/` | Client/borrower entity |
| **Lender.java** | `packs/loan/shared/entity/` | Lender entity |
| **License.java** | `packs/loan/shared/entity/` | License management entity |

### packs/quote (Quote Management)

| File | Location | Purpose |
|------|----------|---------|
| **Quote.java** | `packs/quote/shared/entity/` | Quote entity (shared with pricing) |
| **Rate.java** | `packs/quote/shared/entity/` | Rate entity |
| **Adjustment.java** | `packs/quote/shared/entity/` | Adjustment entity (points, fees) |
| **RateMode.java** | `packs/quote/shared/typekey/` | Rate mode enumeration |
| **LoanType.java** | `packs/quote/shared/typekey/` | Loan type enumeration |
| **LoanChannel.java** | `packs/quote/shared/typekey/` | Loan channel enumeration |

### packs/billing (Billing)

| File | Location | Purpose |
|------|----------|---------|
| **BillingOps.java** | `packs/billing/server/op/` | Billing operations |
| **BillingStatus.java** | `packs/billing/shared/entity/` | Billing status entity |
| **BillingTransaction.java** | `packs/billing/shared/entity/` | Billing transaction entity |

### Documentation

| File | Location | Purpose |
|------|----------|---------|
| **PROJECT_ARCHITECTURE.md** | `/Users/trungthach/IdeaProjects/` | 📚 Detailed architecture guide |
| **MODULE_INTERACTIONS.md** | `/Users/trungthach/IdeaProjects/` | 📚 Data flows and interactions |
| **QUICK_REFERENCE.md** | `/Users/trungthach/IdeaProjects/` | 📚 Quick lookup card |
| **UNDERSTAND_MOSO.md** | `/Users/trungthach/IdeaProjects/` | 📚 THIS FILE - Complete reference |
| **rate-parser.md** | `moso-pricing/docs/` | 📚 Rate extraction architecture |
| **adj-tableinfo.md** | `moso-pricing/docs/` | 📚 Adjustment table structure |
| **adj-pageparser.md** | `moso-pricing/docs/` | 📚 Page parsing logic |
| **adj-conditions.md** | `moso-pricing/docs/` | 📚 Condition resolution |
| **adj-howto-new-parser.md** | `moso-pricing/docs/` | 📚 Guide for adding new lender parsers |
| **CLAUDE.md** | `moso-pricing/` | 📚 AI agent instructions for pricing fixes |
| **CLAUDE.md** | `packs/loan/` | 📚 AI agent instructions for loan operations |

---

## QUICK CODE LOCATION GUIDE

```
Find...                                      Look in...
────────────────────────────────────────────────────────────────────
Main application initialization            moso/src/main/java/com/lenderrate/AppServer.java
All background jobs configuration          moso/src/main/java/com/lenderrate/AppCronConfig.java
Rate/adjustment calculations (KEY!)        moso-pricing/server/op/ComputeAdjustmentOp.java
Quote calculation engine (KEY!)            moso-pricing/server/parser/calculator/QuoteServer.java
Rate mode resolution logic                 moso-pricing/server/parser/calculator/ModeResolver.java
Ratesheet parsing logic                    moso-pricing/server/op/LenderRateLoader.java
Email ratesheet handler                    moso-pricing/RateSheetEmailHandler.java
All lender parsers registry                moso-pricing/server/parser/LenderParserMap.java
Loan lifecycle operations                  packs/loan/server/op/LoanOps.java
Loan business logic                        packs/loan/server/LoanServer.java
Quote entity definition                    packs/quote/shared/entity/Quote.java
Quote operations                           packs/quote/server/op/QuoteOps.java
Billing operations                         packs/billing/server/op/BillingOps.java
HR operations                              packs/hr/server/op/HROps.java
All loan entities (450+)                   packs/loan/shared/entity/
Entity operations (CRUD)                   packs/[module]/server/op/
Entity definitions                         packs/[module]/shared/entity/
GWT frontend code                          moso/src/main/java/com/lenderrate/client/
Cron job implementations                   moso/src/main/java/com/lenderrate/server/op/cron/
Email handlers                             moso/src/main/java/com/lenderrate/server/*MailHandler.java
Type keys & enumerations                   packs/[module]/shared/typekey/
Configuration templates                    moso-configuration/src/main/resources/
Parser documentation                       moso-pricing/docs/
Lender-specific parser docs                moso-pricing/docs/lenders/
Rate parsing patterns                      moso-pricing/docs/rate-parser.md
Adjustment table info                      moso-pricing/docs/adj-tableinfo.md
New lender parser guide                    moso-pricing/docs/adj-howto-new-parser.md
Excel parser tricks                        moso-pricing/docs/excel-parser-tricks.md
Pricing workflow                           moso-pricing/docs/ratesheet-update-process.md
```

---

## BUILD SEQUENCE

### Complete Build (All Modules)

```bash
# 1. Build foundation (defines all dependencies)
cd /Users/trungthach/IdeaProjects/base
mvn clean install

# 2. Build reusable packs (loan, quote, billing, hr, etc.)
cd /Users/trungthach/IdeaProjects/packs
mvn clean install

# 3. Build pricing service
cd /Users/trungthach/IdeaProjects/moso-pricing
mvn clean install

# 4. Build configuration
cd /Users/trungthach/IdeaProjects/moso-configuration
mvn clean install

# 5. Build main application
cd /Users/trungthach/IdeaProjects/moso
mvn clean install

# Result: WAR files ready for deployment
```

### Fast Build (Skip Tests)

```bash
# Skip tests for faster builds during development
mvn clean install -DskipTests

# For moso-pricing, also skip GWT compilation
mvn clean install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true
```

### moso-pricing Special Profiles

```bash
# Default: WAR for App Engine
mvn clean install

# JAR packaging (independent deployment)
mvn clean install -Pjar-packaging

# Skip GWT compilation (faster, for testing only)
mvn clean install -Dgwt.compiler.skip=true

# JAR + skip GWT + skip tests (fastest)
mvn clean install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true
```

---

## COMMON DEVELOPMENT TASKS

### Adding a New Operation

**Example: Add a new operation in moso-pricing**

1. Create operation class:
```java
package com.mosopricing.server.op;

import com.mvu.core.server.AppEngineOp;
import com.mvu.core.server.JSON;

public class MyNewOp extends AppEngineOp {
    public String execute(String jsonParams) {
        // Parse JSON parameters
        Map<String, Object> params = JSON.parse(jsonParams);

        // Validate inputs
        String lenderId = (String) params.get("lenderId");
        if (lenderId == null) {
            return JSON.error("lenderId required");
        }

        // Execute business logic
        Object result = doLogic(lenderId);

        // Return JSON response
        return JSON.stringify(result);
    }

    private Object doLogic(String lenderId) {
        // Your logic here
        return new HashMap<>();
    }
}
```

2. Register in appropriate location (if needed)
3. Call from other operations: `new MyNewOp().execute(jsonParams)`

---

### Adding a New Ratesheet Parser

**See:** `moso-pricing/docs/adj-howto-new-parser.md` (complete guide)

1. Create LenderParser implementation:
```java
public class MyLenderParser extends LenderParser {
    @Override
    public RateData parseRateSheet(File ratesheet) {
        // Parse Excel/PDF
        // Extract rates and adjustments
        return new RateData(...);
    }
}
```

2. Register in `LenderParserMap.java`
3. Document in `moso-pricing/docs/lenders/`

---

### Adding a New Loan Type

1. **Define Type Key** in `packs/loan/shared/typekey/`
2. **Create Entities** in `packs/loan/shared/entity/`
3. **Add Operations** in `packs/loan/server/op/`
4. **Add Parser** if pricing differs in `moso-pricing/server/op/parser/`
5. **Add GWT View** in `moso/client/view/` (if needed)
6. **Add Configuration** in `moso-configuration/src/main/resources/`

---

### Adding a Scheduled Job

1. Create operation class in `moso/server/op/cron/`:
```java
public class MyDailyJobOp extends AppEngineOp {
    public String execute(String jsonParams) {
        // Job logic
        return JSON.stringify(new HashMap<>());
    }
}
```

2. Register in `AppCronConfig.java`:
```java
addDailyJob("myDailyJob", "2:00 AM", new MyDailyJobOp());
```

3. The job will run automatically at scheduled time

---

### Adding Email Handler

1. Create handler class:
```java
public class MyMailHandler extends MailHandlerServlet {
    @Override
    public void handleIncomingEmail(String from, String subject,
                                    String body, List<Attachment> attachments) {
        // Parse email
        // Process attachments
        // Update database
    }
}
```

2. Register in email routing configuration
3. System automatically forwards matching emails

---

### Running Tests

```bash
# Run all tests in module
mvn test

# Run specific test
mvn test -Dtest=MyTest

# Skip integration tests
mvn test -DskipITs

# Run with coverage
mvn test jacoco:report
```

---

## IMPORTANT NOTES

### Critical Services (Don't Break These!)

1. **ComputeAdjustmentOp** (moso-pricing)
   - Used for every rate calculation
   - Must handle QM and NonQM
   - Any change here affects quote accuracy

2. **QuoteServer** (moso-pricing)
   - Core calculation engine
   - Used by ComputeAdjustmentOp
   - Must be performant (called frequently)

3. **ModeResolver** (moso-pricing)
   - Maps quote parameters to rate modes
   - Incorrect mapping = wrong rates
   - Critical for correctness

4. **LoanOps** (packs/loan)
   - Loan lifecycle management
   - Used extensively by moso
   - Many dependent operations

5. **AppServer** (moso)
   - Application initialization
   - Module coordination
   - Must import all necessary packs

---

### Performance Considerations

- **Datastore Latency:** 10-100ms per query (cache aggressively)
- **GWT Compilation:** 30-60 seconds (skip with -Dgwt.compiler.skip=true for testing)
- **Rate Calculation:** Should complete in <500ms per quote
- **Ratesheet Parsing:** 1-5 minutes depending on file size

---

### Common Pitfalls

1. **Building modules out of order:** Always build base → packs → moso-pricing → moso
2. **Not rebuilding moso-pricing after changes:** Changes in packs/quote require rebuild
3. **Forgetting JSON serialization:** All operation results must be valid JSON
4. **Incorrect type keys:** Mismatched rate mode = wrong pricing
5. **Not testing in GWT mode:** JavaScript compilation can reveal issues

---

## NEXT STEPS

Now you have a complete understanding of the MOSO codebase:

1. **For feature development:** Start with operation classes in appropriate module
2. **For rate calculation fixes:** Check moso-pricing/ComputeAdjustmentOp and QuoteServer
3. **For new lender rates:** See moso-pricing/docs/adj-howto-new-parser.md
4. **For loan operations:** Modify packs/loan/server/op/LoanOps.java
5. **For background jobs:** Add to moso/AppCronConfig.java
6. **For UI changes:** Edit GWT views in moso/client/
7. **For scaling:** Deploy moso-pricing independently with -Pjar-packaging

Keep this document updated as architecture evolves!

---

## QUICK LINKS

- 📚 **PROJECT_ARCHITECTURE.md** - Detailed architecture guide
- 📚 **MODULE_INTERACTIONS.md** - Data flows and module interactions
- 📚 **QUICK_REFERENCE.md** - Quick lookup card
- 📚 **moso-pricing/docs/** - Rate parsing and pricing documentation
- 📚 **moso-pricing/CLAUDE.md** - AI agent instructions for pricing
- 📚 **packs/loan/CLAUDE.md** - AI agent instructions for loan operations

---

**Created:** 2026-03-17
**Type:** Consolidated Codebase Reference
**Audience:** Developers, architects, contributors

Use this file as your comprehensive reference for understanding the MOSO project codebase!