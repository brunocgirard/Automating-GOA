# Frontend-First Implementation Plan
## Sales Quote Tool Prototype

## Overview
Build a fully interactive frontend prototype of the Sales Quote Tool using Next.js, React, TypeScript, and Tailwind CSS. The prototype will use mock data (extracted from Excel) and browser localStorage instead of a database, allowing stakeholders to test the complete UX flow before backend investment.

## Strategy: Why Frontend-First?

**Benefits:**
- ✅ Get visual and UX approval early
- ✅ Validate workflows with stakeholders before backend complexity
- ✅ All frontend code reusable when adding backend
- ✅ Faster iteration on design and user flows
- ✅ Stakeholders can interact with real prototype, not wireframes

**What's Real vs Mocked:**
- ✅ **Real:** All UI components, pages, navigation, forms, calculations, filtering, search
- ✅ **Real:** Product selection, quote building, live price calculations
- ✅ **Real:** Quote list, quote editing, form validation
- 🟡 **Mocked:** Products data (JSON file from Excel, ~30 products)
- 🟡 **Mocked:** Quote persistence (localStorage instead of database)
- 🟡 **Mocked:** PDF export (HTML preview styled like PDF)

**Backend Migration Path:**
When approved, we'll add:
1. SQLite database schema
2. API routes (`/api/quotes`, `/api/products`)
3. Replace localStorage with database calls
4. Real PDF generation with @react-pdf/renderer
5. Full Excel catalog import (170+ products)

---

## Tech Stack (Same as PRD)

- **Framework:** Next.js 15 (App Router)
- **UI Library:** React 18
- **Language:** TypeScript
- **Styling:** Tailwind CSS 3.x
- **Components:** Shadcn/UI
- **Icons:** Lucide React
- **Date Handling:** date-fns
- **State:** React Context + localStorage
- **Mock Data:** JSON files (from Excel)

---

## Implementation Phases

### Phase 1: Project Foundation
**Goal:** Working Next.js environment with UI foundation

#### Task 1.1: Initialize Next.js Project
**Steps:**
1. Run `npx create-next-app@latest` with:
   - TypeScript: Yes
   - ESLint: Yes
   - Tailwind CSS: Yes
   - App Router: Yes
   - Import alias: @/*
2. Verify dev server starts: `npm run dev`
3. Clean up default files (keep layout.tsx, page.tsx)

**Files Created:**
- `package.json`
- `tsconfig.json`
- `tailwind.config.ts`
- `next.config.js`
- `src/app/layout.tsx`
- `src/app/page.tsx`

**Verification:**
- Server runs on http://localhost:3000
- No TypeScript errors
- Tailwind CSS working

#### Task 1.2: Install Additional Dependencies
**Commands:**
```bash
npm install date-fns lucide-react
npm install -D @types/node
```

**Dependencies:**
- `date-fns` - Date formatting
- `lucide-react` - Icon library
- `@types/node` - Node types for TypeScript

**Verification:**
- All packages install successfully
- No dependency conflicts

#### Task 1.3: Set Up Shadcn/UI
**Steps:**
1. Initialize Shadcn: `npx shadcn@latest init`
   - Style: Default
   - Base color: Slate
   - CSS variables: Yes
2. Install core components:
   ```bash
   npx shadcn@latest add button
   npx shadcn@latest add input
   npx shadcn@latest add table
   npx shadcn@latest add card
   npx shadcn@latest add select
   npx shadcn@latest add dialog
   npx shadcn@latest add badge
   npx shadcn@latest add separator
   ```

**Files Created:**
- `components/ui/button.tsx`
- `components/ui/input.tsx`
- `components/ui/table.tsx`
- `components/ui/card.tsx`
- `components/ui/select.tsx`
- `components/ui/dialog.tsx`
- `components/ui/badge.tsx`
- `components/ui/separator.tsx`
- `lib/utils.ts`

**Verification:**
- All Shadcn components added
- Can import and use Button component

---

### Phase 2: Mock Data Creation
**Goal:** Extract real product data from Excel for realistic testing

#### Task 2.1: Create Excel to JSON Conversion Script
**File:** `scripts/extract-sample-products.py`

**Script Requirements:**
- Read `QUOTE_CATALOG.xlsx` (Catalog_Master sheet)
- Extract first 30 products (rows 2-32)
- Include columns: ID, Title, Description, Category, Type, Unit Cost, Prereq, Format, Included, System
- Output to `data/products.json`
- Handle missing values gracefully

**Example Output Structure:**
```json
{
  "products": [
    {
      "id": "LBL-001",
      "title": "LabelStar Basic System",
      "description": "Complete labeling system...",
      "category": "Labeling",
      "type": "Machine",
      "unitCost": 25000.00,
      "prereq": null,
      "format": "Standard",
      "included": true,
      "system": "LabelStar",
      "imageUrl": null
    }
  ]
}
```

**Python Packages Needed:**
```bash
pip install openpyxl
```

**Verification:**
- Script runs without errors
- `data/products.json` created
- JSON is valid and parseable
- All 30 products present with correct fields

#### Task 2.2: Create Mock Quote Data Structure
**File:** `data/sample-quotes.json`

**Purpose:** Sample quotes for dashboard testing

**Structure:**
```json
{
  "quotes": [
    {
      "id": "1",
      "projectName": "Acme Corp Line 3",
      "customer": "Acme Corporation",
      "dateCreated": "2026-02-01",
      "dateModified": "2026-02-03",
      "discountRate": 5.0,
      "status": "draft",
      "notes": "Rush delivery requested",
      "items": [
        {
          "productId": "LBL-001",
          "quantity": 1,
          "unitCostOverride": null,
          "includedOverride": null
        }
      ]
    }
  ]
}
```

**Verification:**
- File created with 3-5 sample quotes
- Valid JSON structure
- Quote IDs are unique

#### Task 2.3: Create TypeScript Type Definitions
**File:** `src/lib/types.ts`

**Types to Define:**
```typescript
export interface Product {
  id: string;
  title: string;
  description: string;
  category: string;
  type: 'Machine' | 'Part' | 'Special' | 'Picture';
  unitCost: number;
  prereq: string | null;
  format: string;
  included: boolean;
  system: string | null;
  imageUrl: string | null;
}

export interface QuoteItem {
  productId: string;
  quantity: number;
  unitCostOverride: number | null;
  includedOverride: boolean | null;
}

export interface Quote {
  id: string;
  projectName: string;
  customer: string;
  dateCreated: string;
  dateModified: string | null;
  discountRate: number;
  status: 'draft' | 'sent' | 'approved' | 'rejected';
  notes: string;
  items: QuoteItem[];
}

export interface QuoteCalculations {
  subtotal: number;
  discountAmount: number;
  total: number;
}
```

**Verification:**
- No TypeScript errors
- Types can be imported in other files

---

### Phase 3: Core Components & Layout
**Goal:** Reusable UI components and navigation

#### Task 3.1: Create Layout with Navigation
**Files:**
- `src/components/layout/header.tsx`
- `src/components/layout/nav.tsx`
- Update `src/app/layout.tsx`

**Header Component:**
- Company logo/title
- Navigation links: Dashboard, New Quote, Products
- Styled with Tailwind

**Navigation Component:**
- Active link highlighting
- Responsive (mobile-friendly)
- Using Next.js Link component

**Root Layout:**
- Integrate Header component
- Add global styles
- Set up font (Inter or system font)

**Verification:**
- Navigation visible on all pages
- Links work and show active state
- Responsive on mobile view

#### Task 3.2: Create Product Components
**Files:**
- `src/components/products/product-table.tsx`
- `src/components/products/product-search.tsx`
- `src/components/products/product-filters.tsx`
- `src/components/products/product-detail-modal.tsx`

**ProductTable Component:**
- Display products in table format
- Columns: ID, Title, Category, Type, Unit Cost
- Sortable columns
- Click row to view details
- Uses Shadcn Table component

**ProductSearch Component:**
- Search input field
- Filters by ID, Title, Description (client-side)
- Debounced search (300ms)
- Clear button

**ProductFilters Component:**
- Dropdown for Category filter
- Dropdown for Type filter
- "Clear Filters" button
- Uses Shadcn Select component

**ProductDetailModal Component:**
- Shows all product fields
- Displays in Shadcn Dialog
- "Add to Quote" button (for future)

**Verification:**
- Table displays products correctly
- Search filters results
- Filters work independently and together
- Modal opens with product details

#### Task 3.3: Create Quote Components
**Files:**
- `src/components/quotes/quote-form.tsx`
- `src/components/quotes/quote-items-table.tsx`
- `src/components/quotes/quote-calculations.tsx`
- `src/components/quotes/quote-list-table.tsx`
- `src/components/quotes/product-selector.tsx`

**QuoteForm Component:**
- Inputs: Project Name, Customer, Notes, Discount Rate
- Form validation (required fields)
- Uses Shadcn Input component

**QuoteItemsTable Component:**
- Table of selected products
- Editable quantity (number input)
- Unit cost override input
- Remove button per row
- Shows line total (qty × unit cost)

**QuoteCalculations Component:**
- Display: Subtotal, Discount %, Discount Amount, Total
- Live updates when items/quantities change
- Formatted currency values
- Styled as summary card

**QuoteListTable Component:**
- Display all quotes in table
- Columns: Project Name, Customer, Date Created, Status, Total
- Action buttons: View, Edit, Delete
- Status badges (draft=gray, sent=blue, approved=green)

**ProductSelector Component:**
- Search/browse products to add to quote
- Mini product table with "Add" button
- Search and category filter
- Add button adds product to quote items

**Verification:**
- Form accepts input and validates
- Can add products to quote
- Quantity changes update calculations
- Remove button works
- Calculations accurate
- Quote list displays sample quotes

---

### Phase 4: Page Implementation
**Goal:** Build all main pages with working functionality

#### Task 4.1: Build Product Catalog Page
**File:** `src/app/products/page.tsx`

**Features:**
- Load products from `data/products.json`
- Integrate ProductSearch, ProductFilters, ProductTable
- State management for search term, filters, filtered products
- ProductDetailModal on row click

**Page Layout:**
```
┌─────────────────────────────────┐
│ Header: "Product Catalog"      │
├─────────────────────────────────┤
│ [Search Input]  [Category ▼] [Type ▼] │
├─────────────────────────────────┤
│ Product Table                   │
│ ┌─────┬───────┬────────┬──────┐│
│ │ ID  │ Title │Category│ Cost ││
│ ├─────┼───────┼────────┼──────┤│
│ │ ... │ ...   │ ...    │ ...  ││
│ └─────┴───────┴────────┴──────┘│
└─────────────────────────────────┘
```

**Verification:**
- Page loads with all products
- Search filters products instantly
- Category and Type filters work
- Click product shows modal
- No console errors

#### Task 4.2: Build Quote Builder Page
**File:** `src/app/quotes/new/page.tsx`

**Features:**
- Integrate QuoteForm, ProductSelector, QuoteItemsTable, QuoteCalculations
- State: quote metadata, selected items
- Add product to quote items
- Update quantities
- Remove items
- Calculate totals in real-time
- "Save Draft" button (saves to localStorage)
- "Save & Preview" button (saves and navigates to preview)

**Page Layout:**
```
┌──────────────────────────────────────────┐
│ Header: "Create New Quote"              │
├──────────────────────────────────────────┤
│ Quote Details Form                       │
│ ┌────────────────────────────────────┐  │
│ │ Project Name: [____________]       │  │
│ │ Customer:     [____________]       │  │
│ │ Notes:        [____________]       │  │
│ │ Discount:     [__]%               │  │
│ └────────────────────────────────────┘  │
├──────────────────────────────────────────┤
│ Add Products                             │
│ [Product Selector Component]             │
├──────────────────────────────────────────┤
│ Selected Products                        │
│ [Quote Items Table]                      │
├──────────────────────────────────────────┤
│ Summary                                  │
│ Subtotal:       $XX,XXX.XX              │
│ Discount (5%):  $X,XXX.XX               │
│ Total:          $XX,XXX.XX              │
├──────────────────────────────────────────┤
│ [Save Draft] [Save & Preview]           │
└──────────────────────────────────────────┘
```

**Verification:**
- Can add products from selector
- Quantities update calculations
- Discount applies correctly
- Save Draft stores in localStorage
- Form validation works

#### Task 4.3: Build Quotes Dashboard Page
**File:** `src/app/page.tsx` (home/dashboard)

**Features:**
- Load quotes from localStorage (initially load sample-quotes.json if empty)
- Display QuoteListTable
- Search by project name or customer
- Filter by status
- View button navigates to quote detail
- Edit button navigates to edit page
- Delete button removes from localStorage
- "New Quote" CTA button

**Page Layout:**
```
┌─────────────────────────────────────┐
│ Header: "Quotes Dashboard"         │
│ [+ New Quote] (primary button)     │
├─────────────────────────────────────┤
│ [Search: ________] [Status: All ▼] │
├─────────────────────────────────────┤
│ Quotes Table                        │
│ ┌──────┬────────┬──────┬────────┐  │
│ │Project│Customer│Status│Actions│  │
│ ├──────┼────────┼──────┼────────┤  │
│ │ ...  │ ...    │ ...  │ [...] │  │
│ └──────┴────────┴──────┴────────┘  │
└─────────────────────────────────────┘
```

**Verification:**
- Dashboard loads sample quotes
- Search filters quotes
- Status filter works
- View/Edit buttons navigate correctly
- Delete removes quote
- New Quote button works

#### Task 4.4: Build Quote Detail/Edit Page
**File:** `src/app/quotes/[id]/page.tsx`

**Features:**
- Load quote by ID from localStorage
- Pre-populate QuoteForm with quote data
- Pre-populate QuoteItemsTable with items
- Show calculations
- "Update Quote" button (saves changes to localStorage)
- "Preview PDF" button (navigates to preview)
- "Duplicate Quote" button (creates copy with new ID)
- "Delete Quote" button (removes and redirects to dashboard)

**Page Layout:**
```
┌─────────────────────────────────────┐
│ Header: "Quote: [Project Name]"    │
│ Created: 2026-02-01                │
│ Last Modified: 2026-02-03          │
├─────────────────────────────────────┤
│ [Same layout as Quote Builder]     │
│ ...                                 │
├─────────────────────────────────────┤
│ [Update] [Preview PDF] [Duplicate] [Delete] │
└─────────────────────────────────────┘
```

**Verification:**
- Loads quote correctly
- Edits save to localStorage
- Duplicate creates new quote
- Delete works and redirects
- Preview button navigates to preview

#### Task 4.5: Build Quote Preview/PDF Mockup Page
**File:** `src/app/quotes/[id]/preview/page.tsx`

**Features:**
- Load quote by ID
- Display as styled HTML document that looks like a PDF
- Include:
  - Company branding/logo area (placeholder)
  - Quote header (project, customer, date)
  - Line items table
  - Totals section
  - Terms and conditions (placeholder text)
- "Download PDF" button (shows browser print dialog for now)
- "Back to Edit" button

**Page Layout:**
```
┌─────────────────────────────────────┐
│ [Back to Edit] [Download PDF]      │
├─────────────────────────────────────┤
│ ┌───────────────────────────────┐  │
│ │ [LOGO] Sales Quote            │  │
│ │ Project: Acme Corp Line 3     │  │
│ │ Customer: Acme Corporation    │  │
│ │ Date: February 1, 2026        │  │
│ │                               │  │
│ │ Line Items:                   │  │
│ │ ┌──┬──────┬───┬──────┬──────┐│  │
│ │ │ID│Title │Qty│ Cost │Total ││  │
│ │ ├──┼──────┼───┼──────┼──────┤│  │
│ │ │..│ ...  │.. │ ...  │ ... ││  │
│ │ └──┴──────┴───┴──────┴──────┘│  │
│ │                               │  │
│ │ Subtotal:    $XX,XXX.XX      │  │
│ │ Discount:    $X,XXX.XX       │  │
│ │ Total:       $XX,XXX.XX      │  │
│ │                               │  │
│ │ Terms: [placeholder text]     │  │
│ └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**Styling:**
- White background, centered content
- Print-friendly styles
- Professional formatting
- Looks like a document

**Verification:**
- Preview displays correctly
- All quote data present
- Calculations match
- Print dialog works
- Back button navigates correctly

---

### Phase 5: State Management & Utilities
**Goal:** Centralize data access and business logic

#### Task 5.1: Create LocalStorage Utilities
**File:** `src/lib/storage.ts`

**Functions:**
```typescript
export const QuoteStorage = {
  getAll: (): Quote[] => { ... },
  getById: (id: string): Quote | null => { ... },
  save: (quote: Quote): void => { ... },
  update: (id: string, quote: Quote): void => { ... },
  delete: (id: string): void => { ... },
  generateId: (): string => { ... }
};

export const ProductStorage = {
  getAll: (): Product[] => { ... },
  getById: (id: string): Product | null => { ... }
};
```

**Implementation:**
- Use `localStorage.getItem('quotes')` and `localStorage.setItem('quotes', ...)`
- Parse/stringify JSON
- Handle errors gracefully
- Initialize with sample data if empty

**Verification:**
- Can save and retrieve quotes
- IDs are unique
- Deletes work correctly
- Products load from JSON file

#### Task 5.2: Create Calculation Utilities
**File:** `src/lib/calculations.ts`

**Functions:**
```typescript
export function calculateLineTotal(
  quantity: number,
  unitCost: number
): number { ... }

export function calculateQuoteTotals(
  items: QuoteItem[],
  products: Product[],
  discountRate: number
): QuoteCalculations { ... }
```

**Business Logic:**
- Line total = quantity × (unit cost override || product unit cost)
- Subtotal = sum of all line totals
- Discount amount = subtotal × (discount rate / 100)
- Total = subtotal - discount amount

**Verification:**
- Calculations match expected values
- Handles edge cases (0 items, 0 discount)
- Returns numbers with 2 decimal precision

#### Task 5.3: Create Formatting Utilities
**File:** `src/lib/formatters.ts`

**Functions:**
```typescript
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD'
  }).format(amount);
}

export function formatDate(dateString: string): string {
  return format(new Date(dateString), 'MMMM d, yyyy');
}

export function formatDateShort(dateString: string): string {
  return format(new Date(dateString), 'yyyy-MM-dd');
}
```

**Verification:**
- Currency shows CAD format: $X,XXX.XX
- Dates format correctly
- Handles invalid inputs

---

### Phase 6: Polish & Testing
**Goal:** Ensure professional quality and complete functionality

#### Task 6.1: Add Loading States
**Files:** All page components

**Enhancements:**
- Show loading spinner while data loads
- Skeleton UI for tables (Shadcn Skeleton component)
- Disable buttons during save operations

**Verification:**
- No layout shift during loading
- Loading states visible
- Smooth transitions

#### Task 6.2: Add Error Handling
**Files:** All components with data operations

**Enhancements:**
- Try/catch around localStorage operations
- User-friendly error messages
- Fallback UI for missing data
- Toast notifications for errors (optional: add Shadcn Toast)

**Verification:**
- Graceful failures
- Error messages clear
- App doesn't crash

#### Task 6.3: Add Form Validation
**Files:** `quote-form.tsx`, quote builder page

**Validation Rules:**
- Project Name: Required, max 100 chars
- Customer: Required, max 100 chars
- Discount Rate: Number, 0-100
- Quote must have at least 1 item

**UI Feedback:**
- Show validation errors under fields
- Disable save button if invalid
- Highlight invalid fields

**Verification:**
- Can't save invalid quotes
- Validation messages clear
- Form UX is smooth

#### Task 6.4: Responsive Design Review
**Files:** All components and pages

**Test Breakpoints:**
- Mobile: 375px, 414px
- Tablet: 768px, 1024px
- Desktop: 1280px, 1920px

**Adjustments:**
- Tables scroll horizontally on mobile
- Forms stack vertically on mobile
- Navigation collapses on mobile
- Buttons adapt to screen size

**Verification:**
- Test on mobile viewport
- All features accessible
- No horizontal scroll (except tables)
- Touch-friendly buttons

#### Task 6.5: Accessibility Review
**Files:** All interactive components

**Requirements:**
- Keyboard navigation works
- Focus indicators visible
- Buttons have aria-labels where needed
- Color contrast meets WCAG AA
- Form labels properly associated

**Verification:**
- Tab through entire app
- Check with browser DevTools Lighthouse
- Contrast checker on text/backgrounds

#### Task 6.6: End-to-End Testing
**Test Scenarios:**
1. **Create New Quote Flow:**
   - Navigate to New Quote
   - Fill form
   - Add 3 products
   - Set quantities
   - Apply discount
   - Save draft
   - Verify appears on dashboard

2. **Edit Quote Flow:**
   - Open existing quote
   - Modify customer name
   - Add product
   - Update quantity
   - Save changes
   - Verify changes persisted

3. **Search & Filter Flow:**
   - Search quotes by project name
   - Filter by status
   - Search products by title
   - Filter products by category

4. **Preview Flow:**
   - Open quote
   - Click Preview
   - Verify all data correct
   - Click print/download

5. **Delete Flow:**
   - Delete quote from dashboard
   - Verify removed from list
   - Verify localStorage updated

**Verification Method:**
- Use agent-browser to automate testing
- Take screenshots of each step
- Verify calculations manually
- Check localStorage contents

---

## File Structure (Frontend Only)

```
Demo_Tool_Sales_V2/
├── src/
│   ├── app/
│   │   ├── layout.tsx                  # Root layout with nav
│   │   ├── page.tsx                    # Dashboard (quotes list)
│   │   ├── quotes/
│   │   │   ├── new/
│   │   │   │   └── page.tsx            # Quote builder
│   │   │   └── [id]/
│   │   │       ├── page.tsx            # Quote detail/edit
│   │   │       └── preview/
│   │   │           └── page.tsx        # PDF preview mockup
│   │   ├── products/
│   │   │   └── page.tsx                # Product catalog
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/                         # Shadcn components
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── table.tsx
│   │   │   ├── card.tsx
│   │   │   ├── select.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── badge.tsx
│   │   │   └── separator.tsx
│   │   ├── layout/
│   │   │   ├── header.tsx
│   │   │   └── nav.tsx
│   │   ├── quotes/
│   │   │   ├── quote-form.tsx
│   │   │   ├── quote-items-table.tsx
│   │   │   ├── quote-calculations.tsx
│   │   │   ├── quote-list-table.tsx
│   │   │   └── product-selector.tsx
│   │   └── products/
│   │       ├── product-table.tsx
│   │       ├── product-search.tsx
│   │       ├── product-filters.tsx
│   │       └── product-detail-modal.tsx
│   ├── lib/
│   │   ├── types.ts                    # TypeScript types
│   │   ├── storage.ts                  # localStorage utilities
│   │   ├── calculations.ts             # Business logic
│   │   ├── formatters.ts               # Formatting utilities
│   │   └── utils.ts                    # General utilities (Shadcn)
│   └── styles/
│       └── globals.css
├── data/
│   ├── products.json                   # 30 sample products from Excel
│   └── sample-quotes.json              # Initial sample quotes
├── scripts/
│   └── extract-sample-products.py      # Excel → JSON converter
├── public/
│   └── logo.png                        # Company logo (placeholder)
├── screenshots/                        # Browser testing screenshots
│   └── .gitkeep
├── Original_Files/                     # Keep existing files
│   ├── QUOTE_CATALOG.xlsx
│   ├── Quote_Interface_Test1.xlsm
│   └── QUOTE_LIBRARY.docx
├── .claude/
│   └── settings.json
├── PROMPT.md
├── prd.md
├── activity.md
├── Quote_System_Documentation.md
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.js
```

---

## Migration Path to Backend (After Approval)

When the frontend is approved, we'll add the backend in these steps:

### Step 1: Add Database Layer
- Create SQLite schema (`scripts/schema.sql`)
- Create seed script to import all 170+ products
- Add database utilities (`src/lib/db.ts`)

### Step 2: Create API Routes
- `POST /api/quotes` - Create quote
- `GET /api/quotes` - List quotes
- `GET /api/quotes/[id]` - Get quote
- `PUT /api/quotes/[id]` - Update quote
- `DELETE /api/quotes/[id]` - Delete quote
- `GET /api/products` - List products

### Step 3: Update Frontend
- Replace `QuoteStorage` calls with API fetch calls
- Replace `ProductStorage` calls with API fetch calls
- Add loading states for async operations
- Handle API errors

### Step 4: Add PDF Generation
- Install `@react-pdf/renderer`
- Create PDF template component
- Add `POST /api/quotes/[id]/pdf` endpoint
- Replace preview with real PDF download

### Step 5: Import Full Catalog
- Convert entire QUOTE_CATALOG.xlsx (170+ products)
- Import all product fields (40 columns)
- Update product table to show all categories

**Estimated Migration Time:** 4-6 hours (most code reusable)

---

## Success Criteria

### Frontend Prototype Ready When:
- ✅ All 4 pages functional (Dashboard, New Quote, Products, Preview)
- ✅ Can create quote end-to-end
- ✅ Can edit existing quote
- ✅ Can view quote preview
- ✅ Calculations accurate
- ✅ Search and filters work
- ✅ Responsive on mobile/tablet/desktop
- ✅ No critical bugs
- ✅ Professional appearance
- ✅ Stakeholders can test complete workflow

### Approval Criteria (Stakeholder Review):
- ✅ UI/UX matches expectations
- ✅ Workflow is intuitive
- ✅ Product selection is easy
- ✅ Quote preview looks professional
- ✅ Calculations are correct
- ✅ No major design changes needed

**After approval → Proceed with backend implementation**

---

## Critical Files to Implement

### High Priority (Core Functionality):
1. `src/lib/types.ts` - Type definitions
2. `src/lib/storage.ts` - Data persistence
3. `src/lib/calculations.ts` - Business logic
4. `scripts/extract-sample-products.py` - Mock data
5. `src/components/quotes/quote-form.tsx` - Quote builder
6. `src/components/quotes/quote-items-table.tsx` - Product selection
7. `src/components/quotes/quote-calculations.tsx` - Live totals
8. `src/app/quotes/new/page.tsx` - Quote builder page
9. `src/app/page.tsx` - Dashboard

### Medium Priority (Complete UX):
10. `src/components/products/product-table.tsx` - Product browsing
11. `src/app/products/page.tsx` - Catalog page
12. `src/app/quotes/[id]/page.tsx` - Edit page
13. `src/app/quotes/[id]/preview/page.tsx` - Preview page
14. `src/components/layout/header.tsx` - Navigation

### Low Priority (Polish):
15. Form validation
16. Error handling
17. Loading states
18. Responsive design adjustments
19. Accessibility improvements

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Excel data structure unexpected | Medium | Manually inspect QUOTE_CATALOG.xlsx before scripting |
| LocalStorage size limits | Low | Limit to ~50 quotes (sufficient for prototype) |
| Calculation logic errors | High | Test with known values from existing Excel file |
| Stakeholders want backend immediately | Medium | Explain migration path is only 4-6 hours |
| Different browser localStorage | Low | Test in Chrome/Edge (primary browsers) |

---

## Estimated Timeline

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1: Foundation | 1.1 - 1.3 | 30 mins |
| Phase 2: Mock Data | 2.1 - 2.3 | 1 hour |
| Phase 3: Components | 3.1 - 3.3 | 2 hours |
| Phase 4: Pages | 4.1 - 4.5 | 3 hours |
| Phase 5: State & Utils | 5.1 - 5.3 | 1 hour |
| Phase 6: Polish | 6.1 - 6.6 | 2 hours |
| **Total** | | **~10 hours** |

**With Ralph Wiggum autonomous loop: Estimated 15-25 iterations**

---

## Next Steps After This Plan

1. **Approve this plan** - Review and confirm approach
2. **Update PROMPT.md** - Adjust for frontend-first workflow
3. **Run Ralph loop** - `./ralph.sh 25`
4. **Monitor progress** - Check activity.md and screenshots
5. **Review prototype** - Test at http://localhost:3000
6. **Gather stakeholder feedback**
7. **Decide:** Proceed with backend or iterate on frontend
8. **Migrate to backend** - If approved, add database and API

---

## Key Advantages of This Approach

1. **Fast Time to Demo:** Working prototype in ~10 hours vs 20+ for full stack
2. **Early Validation:** Catch UX issues before backend investment
3. **Stakeholder Buy-In:** Real interactive prototype beats wireframes
4. **Code Reusability:** 80%+ of frontend code reused when adding backend
5. **Low Risk:** If rejected, minimal wasted effort vs full build
6. **Iteration Speed:** Changes take minutes, not hours
7. **Clear Migration Path:** Well-defined backend integration plan

**This plan balances speed with quality while maintaining flexibility for the final backend implementation.**
