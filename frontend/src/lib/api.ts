import type {
  AtRiskSummary,
  LineItem,
  MachineData,
  ProjectCreateRequest,
  ProjectDetail,
  ProjectInsight,
  ProjectListItem,
  StallAlert,
  TaskStatus,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Status = "draft" | "processed" | "ready";

interface ApiQuote {
  id: number;
  quote_ref: string;
  customer_name?: string | null;
  machine_model?: string | null;
  sold_to_address?: string | null;
  ship_to_address?: string | null;
  telephone?: string | null;
  customer_contact_person?: string | null;
  customer_po?: string | null;
  processing_date?: string | null;
  incoterm?: string | null;
  company?: string | null;
  serial_number?: string | null;
  ax?: string | null;
  ox?: string | null;
  via?: string | null;
  tax_id?: string | null;
  hs_code?: string | null;
  customer_number?: string | null;
  order_date?: string | null;
}

interface ApiMachine {
  id: number;
  machine_name: string;
  description?: string | null;
  machine_type?: string | null;
  quote_ref: string;
  client_name?: string | null;
  client_id?: number | null;
  machine_template_id?: number | null;
  status: Status;
  processing_date?: string | null;
  template_data?: Record<string, unknown> | null;
}

interface ApiTemplateResponse {
  id: number;
  template_data: Record<string, unknown>;
  generated_file_path?: string | null;
  processing_date?: string | null;
}

interface ApiPricedItem {
  id: number;
  item_description?: string | null;
  item_quantity?: string | null;
  item_price_str?: string | null;
  item_price_numeric?: number | null;
}

interface ApiQuoteArtifacts {
  quote_ref: string;
  full_pdf_text: string;
  pdf_filename?: string | null;
  items: Array<Record<string, unknown>>;
  machines: Array<Record<string, unknown>>;
}

interface ApiMachineProcessingData {
  machine_id: number;
  quote_ref: string;
  machine_data: Record<string, unknown>;
  main_item?: Record<string, unknown>;
  options?: Array<Record<string, unknown>>;
  common_items?: Array<Record<string, unknown>>;
  full_pdf_text: string;
}

interface ApiReportResponse {
  machine_id: number;
  machine_name: string;
  html: string;
}

interface ApiGoaFormListItem {
  machine_template_id: number;
  machine_id: number;
  quote_ref: string;
  machine_name: string;
  template_type: string;
  generated_file_path?: string | null;
  processing_date?: string | null;
}

interface ApiGoaFormDetail extends ApiGoaFormListItem {
  template_data: Record<string, unknown>;
  output_options?: ApiGoaOutputOptions | null;
  field_labels?: Record<string, string> | null;
  modifications: Array<Record<string, unknown>>;
  html: string;
}

interface ApiGoaFormSaveResponse {
  machine_template_id: number;
  saved_at: string;
  file_path: string;
  html: string;
}

interface ApiGoaOutputOptions {
  included_sections?: string[] | null;
  hide_empty_sections?: boolean;
  hide_empty_fields?: boolean;
  pure_output?: boolean;
  label_overrides?: Record<string, string> | null;
  format?: "html";
}

interface ApiGoaGenerateDocumentResponse {
  machine_template_id: number;
  generated_at: string;
  format: "html" | "docx";
  file_path: string;
  download_url: string;
}

interface ApiGoaFormSchemaField {
  key: string;
  label: string;
  type: "text" | "textarea" | "checkbox" | "number";
}

interface ApiGoaFormSchemaGroup {
  title: string | null;
  fields: ApiGoaFormSchemaField[];
}

interface ApiGoaFormSchemaSection {
  id: string;
  title: string;
  field_count?: number;
  groups: ApiGoaFormSchemaGroup[];
}

interface ApiGoaFormSchemaResponse {
  sections: ApiGoaFormSchemaSection[];
  field_count: number;
}

export interface Client {
  id: string;
  name: string;
  quoteCount: number;
}

export interface QuoteRow {
  id: string;
  quoteId: number;
  quoteRef: string;
  clientId: string;
  clientName: string;
  machineName: string;
  machineDescription: string;
  machineType: string | null;
  machineId: number | null;
  machineTemplateId: number | null;
  status: Status;
  date: string;
}

export interface QuoteDetail {
  id: string;
  quoteId: number;
  machineId: number | null;
  quoteRef: string;
  clientName: string;
  machineName: string;
  status: Status;
  date: string;
  clientInfo: {
    quoteNo: string;
    ax: string;
    customerName: string;
    company: string;
    machine: string;
    serialNumber: string;
    soldToAddress1: string;
    soldToAddress2: string;
    soldToAddress3: string;
    shipToAddress1: string;
    shipToAddress2: string;
    shipToAddress3: string;
    telephone: string;
    customerPO: string;
    orderDate: string;
    ox: string;
    via: string;
    incoterm: string;
    taxId: string;
    hsCode: string;
    customerNumber: string;
    clientContact: string;
  };
  fields: Record<string, { value: string; confidence: number }>;
  lineItems: {
    description: string;
    quantity: string;
    selection: string;
    price: number | null;
  }[];
}

export type QuoteClientInfo = QuoteDetail["clientInfo"];

export interface ProcessingArtifacts {
  quoteRef: string;
  fullPdfText: string;
  pdfFilename: string;
  items: LineItem[];
  machines: MachineData[];
  commonItems: LineItem[];
}

export interface ExtractionResult {
  filled_data: Record<string, string>;
  confidence_scores: Record<string, number>;
  suggestions: Array<Record<string, unknown>>;
  metadata?: ExtractionMetadata | null;
}

export interface ExtractionMetadata {
  pipeline_version?: string;
  pass1_model?: string;
  pass2_model?: string;
  fields_total?: number;
  fields_pass1_attempted?: number;
  fields_pass2_attempted?: number;
  fields_filled_final?: number;
  low_confidence_count?: number;
  timing_ms?: {
    pass1?: number | null;
    pass2?: number | null;
    total?: number | null;
  } | null;
  prompt_chars_estimate?: {
    pass1?: number | null;
    pass2?: number | null;
    total?: number | null;
  } | null;
  critical_text_forced_pass2_count?: number;
  critical_text_overrides_applied?: number;
  critical_text_no_evidence_blanked?: number;
  critical_text_targets?: string[];
}

export interface GeneratedDocumentResult {
  file_path: string;
  machine_id: number | null;
  machine_template_id?: number | null;
}

export interface GoaFormListItem {
  machineTemplateId: number;
  machineId: number;
  quoteRef: string;
  machineName: string;
  templateType: string;
  generatedFilePath: string | null;
  processingDate: string | null;
}

export interface GoaFormDetail extends GoaFormListItem {
  templateData: Record<string, string>;
  outputOptions: GoaOutputOptions | null;
  fieldLabels: Record<string, string>;
  modifications: Array<Record<string, unknown>>;
  html: string;
}

export interface GoaFormSaveResult {
  machineTemplateId: number;
  savedAt: string;
  filePath: string;
  html: string;
}

export interface GoaOutputOptions {
  includedSections?: string[];
  hideEmptySections?: boolean;
  hideEmptyFields?: boolean;
  pureOutput?: boolean;
  labelOverrides?: Record<string, string>;
  format?: "html";
}

export interface GoaGeneratedDocumentResult {
  machineTemplateId: number;
  generatedAt: string;
  format: "html" | "docx";
  filePath: string;
  downloadUrl: string;
}

export interface GoaFormSchemaField {
  key: string;
  label: string;
  type: "text" | "textarea" | "checkbox" | "number";
}

export interface GoaFormSchemaGroup {
  title: string | null;
  fields: GoaFormSchemaField[];
}

export interface GoaFormSchemaSection {
  id: string;
  title: string;
  fieldCount: number;
  groups: GoaFormSchemaGroup[];
}

export interface GoaFormSchemaResponse {
  sections: GoaFormSchemaSection[];
  fieldCount: number;
}

export type ShippingDocumentType =
  | "packing_slip"
  | "commercial_invoice"
  | "certificate_origin"
  | "all";

export type ShippingOutputFormat = "docx" | "html";

interface ApiShippingEnvelope {
  quote_id: number;
  quote_ref: string;
  shipping_data: Record<string, unknown>;
}

interface ApiShippingLoadEnvelope extends ApiShippingEnvelope {
  created_date?: string | null;
  modified_date?: string | null;
}

interface ApiShippingSaveEnvelope extends ApiShippingEnvelope {
  saved_at: string;
}

interface ApiCorEnvelope {
  quote_id: number;
  quote_ref: string;
  cor_data: Record<string, unknown>;
}

interface ApiCorRevisionSummary {
  cor_document_id: number;
  cor_no?: string | null;
  description?: string | null;
  created_date?: string | null;
  modified_date?: string | null;
}

interface ApiCorRevisionListEnvelope {
  quote_id: number;
  quote_ref: string;
  revisions: ApiCorRevisionSummary[];
}

interface ApiCorLoadEnvelope extends ApiCorEnvelope {
  cor_document_id: number;
  cor_no?: string | null;
  description?: string | null;
  created_date?: string | null;
  modified_date?: string | null;
}

interface ApiCorSaveEnvelope extends ApiCorEnvelope {
  cor_document_id: number;
  cor_no?: string | null;
  description?: string | null;
  saved_at: string;
}

interface ApiProjectTask {
  id: number;
  project_id: number;
  task_name: string;
  task_order: number;
  phase: string;
  status: string;
  planned_date?: string | null;
  actual_date?: string | null;
  notes?: string | null;
  modified_date?: string | null;
}

interface ApiProjectListItem {
  id: number;
  project_name: string;
  customer_name: string;
  quote_ref?: string | null;
  machine_summary?: string | null;
  status: string;
  risk_level: string;
  current_phase?: string | null;
  current_task?: string | null;
  days_in_phase?: number | null;
  progress_pct?: number;
  start_date?: string | null;
  target_end_date?: string | null;
  actual_end_date?: string | null;
  created_date?: string | null;
  modified_date?: string | null;
}

interface ApiProjectDetail extends ApiProjectListItem {
  tasks?: ApiProjectTask[];
  gantt_data?: Record<string, unknown> | null;
}

interface ApiAtRiskSummary {
  count: number;
  projects?: Array<{
    project_id?: number | null;
    name?: string | null;
    task?: string | null;
    phase?: string | null;
    days_stalled?: number | null;
  }>;
}

interface ApiInsight {
  project_id?: number | null;
  project_name?: string | null;
  task_id?: number | null;
  task_name?: string | null;
  type?: string | null;
  severity?: "critical" | "warning" | "info" | null;
  title?: string | null;
  message?: string | null;
  phase?: string | null;
  days_stalled?: number | null;
}

export interface ShippingCrate {
  id: string;
  lengthIn: string;
  widthIn: string;
  heightIn: string;
  weightLbs: string;
}

export interface ShippingTruck {
  id: string;
  name: string;
}

export interface ShippingMachine {
  id: string;
  machineId: number | null;
  lineItemOptionId: string | null;
  machineName: string;
  model: string;
  hsCode: string;
  serialNumber: string;
  unitPrice: number;
  truckId: string;
  crates: ShippingCrate[];
}

export interface ShippingLineItemOption {
  id: string;
  lineItemId: number | null;
  name: string;
  description: string;
  quantity: string;
  unitPrice: number;
}

export interface ShippingClientInfo {
  quoteRef: string;
  company: string;
  customerName: string;
  soldToAddress1: string;
  soldToAddress2: string;
  soldToAddress3: string;
  shipToAddress1: string;
  shipToAddress2: string;
  shipToAddress3: string;
  telephone: string;
  customerPO: string;
  orderDate: string;
  ax: string;
  ox: string;
  via: string;
  incoterm: string;
  taxId: string;
  customerNumber: string;
  clientContact: string;
}

export interface ShippingMeta {
  brokerInfo: string;
  blanketFrom: string;
  blanketTo: string;
  originCriterion: string;
  certifierName: string;
  certifierTitle: string;
  certifierDate: string;
  certifierContact: string;
  totalInvoiceAmount: string;
  countryOfOrigin: string;
}

export interface ShippingDocumentState {
  quoteId: number;
  quoteRef: string;
  client: ShippingClientInfo;
  machines: ShippingMachine[];
  lineItemOptions: ShippingLineItemOption[];
  trucks: ShippingTruck[];
  meta: ShippingMeta;
}

export interface ShippingLoadResult {
  quoteId: number;
  quoteRef: string;
  createdDate: string | null;
  modifiedDate: string | null;
  shippingData: ShippingDocumentState;
}

export interface ShippingSaveResult {
  quoteId: number;
  quoteRef: string;
  savedAt: string;
  shippingData: ShippingDocumentState;
}

export interface CorLineItem {
  id: string;
  qty: string;
  reqDescription: string;
  unitCost: string;
  selectedItems: string;
}

export interface CorClientInfo {
  company: string;
  customerPO: string;
  orderDate: string;
  ax: string;
  ox: string;
  machine: string;
}

export interface CorDocumentState {
  quoteId: number;
  quoteRef: string;
  client: CorClientInfo;
  corNo: string;
  revisionDescription: string;
  corStatus: string;
  capmaticPM: string;
  initiatorOfChange: string;
  salesRep: string;
  contactPerson: string;
  impactDeliverables: string;
  impactDeliveryDate: string;
  paymentTerms: string;
  currency: string;
  approvalDate: string;
  justificationForChange: string;
  comments: string;
  lineItems: CorLineItem[];
}

export interface CorRevisionSummary {
  corDocumentId: number;
  corNo: string;
  description: string;
  createdDate: string | null;
  modifiedDate: string | null;
}

export interface CorRevisionListResult {
  quoteId: number;
  quoteRef: string;
  revisions: CorRevisionSummary[];
}

export interface CorLoadResult {
  quoteId: number;
  quoteRef: string;
  corDocumentId: number;
  corNo: string;
  description: string;
  createdDate: string | null;
  modifiedDate: string | null;
  corData: CorDocumentState;
}

export interface CorSaveResult {
  quoteId: number;
  quoteRef: string;
  corDocumentId: number;
  corNo: string;
  description: string;
  savedAt: string;
  corData: CorDocumentState;
}

export interface QuoteWorkflowStatus {
  quoteId: number;
  quoteRef: string;
  quoteStatus: Status;
  quoteProcessed: boolean;
  shippingSaved: boolean;
  shippingModifiedDate: string | null;
  corSaved: boolean;
  corModifiedDate: string | null;
}

function createClientId(name: string, fallback: string): string {
  const normalized = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return normalized || `client-${fallback}`;
}

function toDateOnly(value: string | null | undefined): string {
  if (!value) return "";
  const [date] = value.split(" ");
  return date ?? value;
}

function splitAddressLines(value: string | null | undefined): [string, string, string] {
  if (!value) return ["", "", ""];
  const lines = value.split(/\r?\n/);
  return [
    lines[0]?.trim() ?? "",
    lines[1]?.trim() ?? "",
    lines.slice(2).join("\n").trim(),
  ];
}

function joinAddressLines(line1: string, line2: string, line3: string): string {
  return [line1, line2, line3]
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .join("\n");
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string {
  if (value == null) return "";
  return String(value);
}

function asNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const parsed = Number(asString(value).replace(/[^0-9.-]/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeShippingDownloadFilename(
  filename: string,
  documentType: ShippingDocumentType,
  contentType: string,
  outputFormat: ShippingOutputFormat
): string {
  const normalizedType = contentType.toLowerCase();
  const isZipResponse =
    normalizedType.includes("application/zip") ||
    normalizedType.includes("application/x-zip-compressed");
  const isHtmlResponse = normalizedType.includes("text/html");

  let candidate = filename.trim();
  if (!candidate) {
    if (documentType === "all" || isZipResponse) {
      candidate = documentType === "all" ? "shipping-documents.zip" : `${documentType}.zip`;
    } else if (outputFormat === "html" || isHtmlResponse) {
      candidate = `${documentType}.html`;
    } else {
      candidate = `${documentType}.docx`;
    }
  }

  if (isZipResponse && !candidate.toLowerCase().endsWith(".zip")) {
    candidate = candidate.replace(/\.[a-z0-9]+$/i, "");
    candidate = `${candidate}.zip`;
  }
  if (!isZipResponse && (outputFormat === "html" || isHtmlResponse) && !candidate.toLowerCase().endsWith(".html")) {
    candidate = candidate.replace(/\.[a-z0-9]+$/i, "");
    candidate = `${candidate}.html`;
  }
  return candidate;
}

function normalizeCorDownloadFilename(filename: string, contentType: string): string {
  const normalizedType = contentType.toLowerCase();
  const isZipResponse =
    normalizedType.includes("application/zip") ||
    normalizedType.includes("application/x-zip-compressed");
  let candidate = filename.trim();
  if (!candidate) {
    candidate = isZipResponse ? "cor-documents.zip" : "cor.docx";
  }
  if (isZipResponse && !candidate.toLowerCase().endsWith(".zip")) {
    candidate = candidate.replace(/\.[a-z0-9]+$/i, "");
    candidate = `${candidate}.zip`;
  }
  if (!isZipResponse && !candidate.toLowerCase().endsWith(".docx")) {
    candidate = candidate.replace(/\.[a-z0-9]+$/i, "");
    candidate = `${candidate}.docx`;
  }
  return candidate;
}

function normalizeProjectPhase(
  value: string | null | undefined
): "sales_onboarding" | "engineering_prep" | "design_approval" | "production" | "delivery" | null {
  const normalized = asString(value).trim().toLowerCase();
  if (
    normalized === "sales_onboarding" ||
    normalized === "engineering_prep" ||
    normalized === "design_approval" ||
    normalized === "production" ||
    normalized === "delivery"
  ) {
    return normalized;
  }
  return null;
}

function normalizeTaskStatus(value: string | null | undefined): TaskStatus {
  const normalized = asString(value).trim().toLowerCase();
  if (normalized === "in_progress" || normalized === "done" || normalized === "skipped") {
    return normalized;
  }
  return "pending";
}

function normalizeRiskLevel(value: string | null | undefined): "on_track" | "at_risk" | "overdue" {
  const normalized = asString(value).trim().toLowerCase();
  if (normalized === "at_risk" || normalized === "overdue") return normalized;
  return "on_track";
}

function normalizeProjectTask(task: ApiProjectTask): ProjectDetail["tasks"][number] {
  return {
    id: task.id,
    project_id: task.project_id,
    task_name: asString(task.task_name),
    task_order: Number(task.task_order) || 0,
    phase: normalizeProjectPhase(task.phase) ?? "production",
    status: normalizeTaskStatus(task.status),
    planned_date: task.planned_date ?? null,
    actual_date: task.actual_date ?? null,
    notes: task.notes ?? null,
    modified_date: task.modified_date ?? null,
  };
}

function normalizeProjectListItem(project: ApiProjectListItem): ProjectListItem {
  return {
    id: project.id,
    project_name: asString(project.project_name),
    customer_name: asString(project.customer_name),
    quote_ref: project.quote_ref ?? null,
    machine_summary: project.machine_summary ?? null,
    status: asString(project.status) || "active",
    risk_level: normalizeRiskLevel(project.risk_level),
    current_phase: normalizeProjectPhase(project.current_phase),
    current_task: project.current_task ?? null,
    days_in_phase:
      typeof project.days_in_phase === "number" && Number.isFinite(project.days_in_phase)
        ? project.days_in_phase
        : null,
    progress_pct:
      typeof project.progress_pct === "number" && Number.isFinite(project.progress_pct)
        ? project.progress_pct
        : 0,
    start_date: project.start_date ?? null,
    target_end_date: project.target_end_date ?? null,
    actual_end_date: project.actual_end_date ?? null,
    created_date: project.created_date ?? null,
    modified_date: project.modified_date ?? null,
  };
}

function normalizeProjectDetail(project: ApiProjectDetail): ProjectDetail {
  return {
    ...normalizeProjectListItem(project),
    tasks: (project.tasks ?? []).map((task) => normalizeProjectTask(task)),
    gantt_data: project.gantt_data ?? null,
  };
}

function normalizeProjectInsight(value: ApiInsight): ProjectInsight {
  const severityRaw = asString(value.severity).toLowerCase();
  const severity: "critical" | "warning" | "info" =
    severityRaw === "critical" || severityRaw === "warning" || severityRaw === "info"
      ? severityRaw
      : "info";
  return {
    project_id: typeof value.project_id === "number" ? value.project_id : null,
    project_name: value.project_name ?? null,
    task_id: typeof value.task_id === "number" ? value.task_id : null,
    task_name: value.task_name ?? null,
    type: asString(value.type) || "info",
    severity,
    title: asString(value.title) || "Insight",
    message: asString(value.message),
    phase: value.phase ?? null,
    days_stalled:
      typeof value.days_stalled === "number" && Number.isFinite(value.days_stalled)
        ? value.days_stalled
        : null,
  };
}

function normalizeCorState(
  rawState: unknown,
  quoteIdFallback: number,
  quoteRefFallback: string
): CorDocumentState {
  const state = asRecord(rawState);
  const clientRaw = asRecord(state.client);
  const lineItemsRaw = Array.isArray(state.lineItems) ? state.lineItems : [];

  const lineItems: CorLineItem[] = lineItemsRaw
    .map((entry, index) => {
      const row = asRecord(entry);
      return {
        id: asString(row.id) || `cor-line-${index + 1}`,
        qty: asString(row.qty),
        reqDescription: asString(row.reqDescription),
        unitCost: asString(row.unitCost),
        selectedItems: asString(row.selectedItems),
      };
    })
    .filter((row) => row.qty || row.reqDescription || row.unitCost || row.selectedItems);

  return {
    quoteId:
      typeof state.quoteId === "number" && Number.isFinite(state.quoteId)
        ? state.quoteId
        : quoteIdFallback,
    quoteRef: asString(state.quoteRef) || quoteRefFallback,
    client: {
      company: asString(clientRaw.company),
      customerPO: asString(clientRaw.customerPO),
      orderDate: asString(clientRaw.orderDate),
      ax: asString(clientRaw.ax),
      ox: asString(clientRaw.ox),
      machine: asString(clientRaw.machine),
    },
    corNo: asString(state.corNo) || "1",
    revisionDescription: asString(state.revisionDescription),
    corStatus: asString(state.corStatus),
    capmaticPM: asString(state.capmaticPM),
    initiatorOfChange: asString(state.initiatorOfChange) || "contact_person",
    salesRep: asString(state.salesRep),
    contactPerson: asString(state.contactPerson),
    impactDeliverables: asString(state.impactDeliverables),
    impactDeliveryDate: asString(state.impactDeliveryDate),
    paymentTerms: asString(state.paymentTerms),
    currency: asString(state.currency),
    approvalDate: asString(state.approvalDate),
    justificationForChange: asString(state.justificationForChange),
    comments: asString(state.comments),
    lineItems:
      lineItems.length > 0
        ? lineItems
        : [{ id: "cor-line-1", qty: "", reqDescription: "", unitCost: "", selectedItems: "" }],
  };
}

function normalizeLineItemName(rawName: string, description: string): string {
  const source = (rawName || description || "").split(/\r?\n/)[0] ?? "";
  let value = source.replace(/\s+/g, " ").trim().replace(/^[\s\-:;,.]+|[\s\-:;,.]+$/g, "");
  value = value.replace(/([A-Za-z0-9])\s*-\s*([A-Za-z0-9])/g, "$1-$2");
  if (!value) return "";

  const modelMatch = value.match(/\bmodel\b[:\s-]*(.+)$/i);
  if (modelMatch?.[1]) {
    const model = modelMatch[1]
      .replace(/\s+/g, " ")
      .trim()
      .replace(/^[\s\-:;,.]+|[\s\-:;,.]+$/g, "")
      .replace(/([A-Za-z0-9])\s*-\s*([A-Za-z0-9])/g, "$1-$2");
    if (model) return model;
  }
  return value;
}

function normalizeShippingState(
  rawState: unknown,
  quoteIdFallback: number,
  quoteRefFallback: string
): ShippingDocumentState {
  const state = asRecord(rawState);
  const clientRaw = asRecord(state.client);
  const metaRaw = asRecord(state.meta);
  const lineItemOptionsRaw = Array.isArray(state.lineItemOptions)
    ? state.lineItemOptions
    : [];
  const lineItemOptions: ShippingLineItemOption[] = lineItemOptionsRaw
    .map((entry, index) => {
      const option = asRecord(entry);
      const description = asString(option.description);
      const name = normalizeLineItemName(asString(option.name), description);
      return {
        id: asString(option.id) || `line-item-${index + 1}`,
        lineItemId:
          typeof option.lineItemId === "number" && Number.isFinite(option.lineItemId)
            ? option.lineItemId
            : null,
        name: name || description,
        description,
        quantity: asString(option.quantity),
        unitPrice: asNumber(option.unitPrice),
      };
    })
    .filter((option) => option.name || option.description);
  const lineItemNameById = new Map(
    lineItemOptions.map((option) => [option.id, option.name || option.description] as const)
  );

  const machinesRaw = Array.isArray(state.machines) ? state.machines : [];
  const machines: ShippingMachine[] = machinesRaw
    .map((entry, index) => {
      const machine = asRecord(entry);
      const cratesRaw = Array.isArray(machine.crates) ? machine.crates : [];
      const crates: ShippingCrate[] = cratesRaw.map((crateEntry, crateIndex) => {
        const crate = asRecord(crateEntry);
        return {
          id: asString(crate.id) || `crate-${index + 1}-${crateIndex + 1}`,
          lengthIn: asString(crate.lengthIn),
          widthIn: asString(crate.widthIn),
          heightIn: asString(crate.heightIn),
          weightLbs: asString(crate.weightLbs),
        };
      });

      return {
        id: asString(machine.id) || `machine-${index + 1}`,
        machineId:
          typeof machine.machineId === "number" && Number.isFinite(machine.machineId)
            ? machine.machineId
            : null,
        lineItemOptionId: asString(machine.lineItemOptionId) || null,
        machineName:
          lineItemNameById.get(asString(machine.lineItemOptionId)) ||
          asString(machine.machineName),
        model:
          lineItemNameById.get(asString(machine.lineItemOptionId)) ||
          asString(machine.model),
        hsCode: asString(machine.hsCode),
        serialNumber: asString(machine.serialNumber),
        unitPrice: asNumber(machine.unitPrice),
        truckId: asString(machine.truckId) || "truck-1",
        crates: crates.length > 0 ? crates : [{ id: `crate-${index + 1}-1`, lengthIn: "", widthIn: "", heightIn: "", weightLbs: "" }],
      };
    })
    .filter((machine) => machine.machineName || machine.model);

  const trucksRaw = Array.isArray(state.trucks) ? state.trucks : [];
  const trucks: ShippingTruck[] = trucksRaw
    .map((entry, index) => {
      const truck = asRecord(entry);
      return {
        id: asString(truck.id) || `truck-${index + 1}`,
        name: asString(truck.name) || `Truck ${index + 1}`,
      };
    })
    .filter((truck) => truck.id);

  return {
    quoteId:
      typeof state.quoteId === "number" && Number.isFinite(state.quoteId)
        ? state.quoteId
        : quoteIdFallback,
    quoteRef: asString(state.quoteRef) || quoteRefFallback,
    client: {
      quoteRef: asString(clientRaw.quoteRef) || quoteRefFallback,
      company: asString(clientRaw.company),
      customerName: asString(clientRaw.customerName),
      soldToAddress1: asString(clientRaw.soldToAddress1),
      soldToAddress2: asString(clientRaw.soldToAddress2),
      soldToAddress3: asString(clientRaw.soldToAddress3),
      shipToAddress1: asString(clientRaw.shipToAddress1),
      shipToAddress2: asString(clientRaw.shipToAddress2),
      shipToAddress3: asString(clientRaw.shipToAddress3),
      telephone: asString(clientRaw.telephone),
      customerPO: asString(clientRaw.customerPO),
      orderDate: asString(clientRaw.orderDate),
      ax: asString(clientRaw.ax),
      ox: asString(clientRaw.ox),
      via: asString(clientRaw.via),
      incoterm: asString(clientRaw.incoterm),
      taxId: asString(clientRaw.taxId),
      customerNumber: asString(clientRaw.customerNumber),
      clientContact: asString(clientRaw.clientContact),
    },
    machines,
    lineItemOptions,
    trucks: trucks.length > 0 ? trucks : [{ id: "truck-1", name: "Truck 1" }],
    meta: {
      brokerInfo: asString(metaRaw.brokerInfo),
      blanketFrom: asString(metaRaw.blanketFrom),
      blanketTo: asString(metaRaw.blanketTo),
      originCriterion: asString(metaRaw.originCriterion) || "B",
      certifierName: asString(metaRaw.certifierName),
      certifierTitle: asString(metaRaw.certifierTitle) || "Project Manager",
      certifierDate: asString(metaRaw.certifierDate),
      certifierContact: asString(metaRaw.certifierContact),
      totalInvoiceAmount: asString(metaRaw.totalInvoiceAmount),
      countryOfOrigin: asString(metaRaw.countryOfOrigin) || "Canada",
    },
  };
}

function toTimestamp(value: string): number {
  const n = Date.parse(value);
  return Number.isNaN(n) ? 0 : n;
}

function aggregateQuoteStatus(machineRows: ApiMachine[]): Status {
  if (machineRows.some((row) => row.status === "ready")) {
    return "ready";
  }
  if (machineRows.some((row) => row.status === "processed")) {
    return "processed";
  }
  return "draft";
}

async function fetchJson<T>(
  path: string,
  options?: RequestInit,
  allow404 = false
): Promise<T | null> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (allow404 && res.status === 404) {
    return null;
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }

  if (res.status === 204) {
    return null;
  }
  return (await res.json()) as T;
}

async function fetchQuoteRowsInternal(): Promise<QuoteRow[]> {
  const [quotesResponse, machinesResponse] = await Promise.all([
    fetchJson<ApiQuote[]>("/api/quotes"),
    fetchJson<ApiMachine[]>("/api/machines/all?main_only=true"),
  ]);

  const quotes = quotesResponse ?? [];
  const machines = machinesResponse ?? [];

  const machinesByQuoteId = new Map<number, ApiMachine[]>();
  const machinesByQuoteRef = new Map<string, ApiMachine[]>();

  for (const machine of machines) {
    if (typeof machine.client_id === "number") {
      const groupedById = machinesByQuoteId.get(machine.client_id);
      if (groupedById) {
        groupedById.push(machine);
      } else {
        machinesByQuoteId.set(machine.client_id, [machine]);
      }
    }

    if (typeof machine.quote_ref === "string" && machine.quote_ref) {
      const groupedByRef = machinesByQuoteRef.get(machine.quote_ref);
      if (groupedByRef) {
        groupedByRef.push(machine);
      } else {
        machinesByQuoteRef.set(machine.quote_ref, [machine]);
      }
    }
  }

  const rows: QuoteRow[] = [];
  for (const quote of quotes) {
    const quoteMachines = machinesByQuoteId.get(quote.id) ?? machinesByQuoteRef.get(quote.quote_ref) ?? [];
    const clientName = (quote.customer_name ?? "").trim() || "Unknown Client";
    const clientId = createClientId(clientName, String(quote.id));
    const quoteDate = toDateOnly(quote.processing_date);

    if (quoteMachines.length === 0) {
      rows.push({
        id: `${quote.id}:none`,
        quoteId: quote.id,
        quoteRef: quote.quote_ref,
        clientId,
        clientName,
        machineName: quote.machine_model || "Unassigned Machine",
        machineDescription: "",
        machineType: null,
        machineId: null,
        machineTemplateId: null,
        status: "draft",
        date: quoteDate,
      });
      continue;
    }

    for (const machine of quoteMachines) {
      rows.push({
        id: `${quote.id}:${machine.id}`,
        quoteId: quote.id,
        quoteRef: quote.quote_ref,
        clientId,
        clientName,
        machineName: machine.machine_name,
        machineDescription: machine.description ?? "",
        machineType: machine.machine_type ?? null,
        machineId: machine.id,
        machineTemplateId:
          typeof machine.machine_template_id === "number" ? machine.machine_template_id : null,
        status: machine.status,
        date: toDateOnly(machine.processing_date) || quoteDate,
      });
    }
  }

  rows.sort((a, b) => toTimestamp(b.date) - toTimestamp(a.date));
  return rows;
}

function normalizeItem(item: Record<string, unknown>): LineItem {
  const description =
    (typeof item.description === "string" && item.description) ||
    (typeof item.item_description === "string" && item.item_description) ||
    "";
  const quantityText =
    (typeof item.quantity_text === "string" && item.quantity_text) ||
    (typeof item.item_quantity === "string" && item.item_quantity) ||
    "";
  const selectionText =
    (typeof item.selection_text === "string" && item.selection_text) ||
    (typeof item.item_price_str === "string" && item.item_price_str) ||
    "";
  const price =
    typeof item.item_price_numeric === "number" ? item.item_price_numeric : null;

  return {
    description,
    quantity_text: quantityText,
    selection_text: selectionText,
    item_price_numeric: price,
  };
}

export async function fetchQuotes(clientId?: string): Promise<QuoteRow[]> {
  const rows = await fetchQuoteRowsInternal();
  if (!clientId || clientId === "__all__") return rows;
  return rows.filter((row) => row.clientId === clientId);
}

export async function fetchClients(): Promise<Client[]> {
  const rows = await fetchQuoteRowsInternal();
  const grouped = new Map<string, Client>();
  for (const row of rows) {
    const current = grouped.get(row.clientId);
    if (!current) {
      grouped.set(row.clientId, { id: row.clientId, name: row.clientName, quoteCount: 1 });
    } else {
      current.quoteCount += 1;
    }
  }
  return Array.from(grouped.values()).sort((a, b) => a.name.localeCompare(b.name));
}

export async function getQuoteDetail(
  quoteId: string | number,
  machineId?: number | null
): Promise<QuoteDetail> {
  const parsedQuoteId = Number(quoteId);
  if (!Number.isFinite(parsedQuoteId)) {
    throw new Error("Invalid quote id.");
  }

  const quote = await fetchJson<ApiQuote>(`/api/quotes/${parsedQuoteId}`);
  if (!quote) {
    throw new Error("Quote not found.");
  }

  const machines =
    (await fetchJson<ApiMachine[]>(`/api/quotes/${parsedQuoteId}/machines`, undefined, true)) ?? [];
  const selectedMachine =
    (machineId ? machines.find((machine) => machine.id === machineId) : undefined) ?? machines[0];

  const template =
    selectedMachine?.id != null
      ? await fetchJson<ApiTemplateResponse>(
          `/api/machines/${selectedMachine.id}/template?template_type=GOA`,
          undefined,
          true
        )
      : null;

  const apiItems =
    (await fetchJson<ApiPricedItem[]>(
      `/api/processing/items/${encodeURIComponent(quote.quote_ref)}`,
      undefined,
      true
    )) ?? [];

  const fields: Record<string, { value: string; confidence: number }> = {};
  if (template?.template_data) {
    for (const [key, value] of Object.entries(template.template_data)) {
      fields[key] = {
        value: value == null ? "" : String(value),
        confidence: 0.9,
      };
    }
  } else {
    fields.machine_model = {
      value: selectedMachine?.machine_name || quote.machine_model || "",
      confidence: 0.8,
    };
    fields.customer_name = {
      value: quote.customer_name || "",
      confidence: 0.8,
    };
  }

  const lineItems = apiItems.map((item) => ({
    description: item.item_description ?? "",
    quantity: item.item_quantity ?? "",
    selection: item.item_price_str ?? "",
    price: item.item_price_numeric ?? null,
  }));

  const [soldToAddress1, soldToAddress2, soldToAddress3] = splitAddressLines(quote.sold_to_address);
  const [shipToAddress1, shipToAddress2, shipToAddress3] = splitAddressLines(quote.ship_to_address);

  return {
    id: String(quote.id),
    quoteId: quote.id,
    machineId: selectedMachine?.id ?? null,
    quoteRef: quote.quote_ref,
    clientName: quote.customer_name || "Unknown Client",
    machineName: selectedMachine?.machine_name || quote.machine_model || "Unassigned Machine",
    status: selectedMachine?.status ?? "draft",
    date: toDateOnly(selectedMachine?.processing_date) || toDateOnly(quote.processing_date),
    clientInfo: {
      quoteNo: quote.quote_ref || "",
      ax: quote.ax || "",
      customerName: quote.customer_name || "",
      company: quote.company || "",
      machine: quote.machine_model || "",
      serialNumber: quote.serial_number || "",
      soldToAddress1,
      soldToAddress2,
      soldToAddress3,
      shipToAddress1,
      shipToAddress2,
      shipToAddress3,
      telephone: quote.telephone || "",
      customerPO: quote.customer_po || "",
      orderDate: quote.order_date || "",
      ox: quote.ox || "",
      via: quote.via || "",
      incoterm: quote.incoterm || "",
      taxId: quote.tax_id || "",
      hsCode: quote.hs_code || "",
      customerNumber: quote.customer_number || "",
      clientContact: quote.customer_contact_person || "",
    },
    fields,
    lineItems,
  };
}

export async function fetchQuoteClientInfo(quoteId: number): Promise<QuoteClientInfo> {
  if (!Number.isFinite(quoteId)) {
    throw new Error("Invalid quote id.");
  }
  const quote = await fetchJson<ApiQuote>(`/api/quotes/${quoteId}`);
  if (!quote) {
    throw new Error("Quote not found.");
  }
  const [soldToAddress1, soldToAddress2, soldToAddress3] = splitAddressLines(quote.sold_to_address);
  const [shipToAddress1, shipToAddress2, shipToAddress3] = splitAddressLines(quote.ship_to_address);
  return {
    quoteNo: quote.quote_ref || "",
    ax: quote.ax || "",
    customerName: quote.customer_name || "",
    company: quote.company || "",
    machine: quote.machine_model || "",
    serialNumber: quote.serial_number || "",
    soldToAddress1,
    soldToAddress2,
    soldToAddress3,
    shipToAddress1,
    shipToAddress2,
    shipToAddress3,
    telephone: quote.telephone || "",
    customerPO: quote.customer_po || "",
    orderDate: quote.order_date || "",
    ox: quote.ox || "",
    via: quote.via || "",
    incoterm: quote.incoterm || "",
    taxId: quote.tax_id || "",
    hsCode: quote.hs_code || "",
    customerNumber: quote.customer_number || "",
    clientContact: quote.customer_contact_person || "",
  };
}

export async function fetchQuoteWorkflowStatus(
  quoteId: number
): Promise<QuoteWorkflowStatus> {
  if (!Number.isFinite(quoteId)) {
    throw new Error("Invalid quote id.");
  }

  const [quote, machines, shippingState, corState] = await Promise.all([
    fetchJson<ApiQuote>(`/api/quotes/${quoteId}`),
    fetchJson<ApiMachine[]>(
      `/api/quotes/${quoteId}/machines?main_only=true`,
      undefined,
      true
    ),
    fetchJson<ApiShippingLoadEnvelope>(
      `/api/shipping/${quoteId}/load`,
      undefined,
      true
    ),
    fetchJson<ApiCorLoadEnvelope>(`/api/cor/${quoteId}/load`, undefined, true),
  ]);

  if (!quote) {
    throw new Error("Quote not found.");
  }

  const machineRows = machines ?? [];
  const quoteStatus = aggregateQuoteStatus(machineRows);

  return {
    quoteId: quote.id,
    quoteRef: quote.quote_ref,
    quoteStatus,
    quoteProcessed: quoteStatus !== "draft",
    shippingSaved: Boolean(shippingState),
    shippingModifiedDate: shippingState?.modified_date ?? null,
    corSaved: Boolean(corState),
    corModifiedDate: corState?.modified_date ?? null,
  };
}

export async function fetchAtRiskSummary(): Promise<AtRiskSummary> {
  const response = await fetchJson<ApiAtRiskSummary>("/api/pm/at-risk");
  if (!response) {
    return { count: 0, projects: [] };
  }
  return {
    count: typeof response.count === "number" ? response.count : 0,
    projects: (response.projects ?? []).map((entry) => ({
      project_id: typeof entry.project_id === "number" ? entry.project_id : null,
      name: asString(entry.name),
      task: asString(entry.task),
      phase: asString(entry.phase),
      days_stalled:
        typeof entry.days_stalled === "number" && Number.isFinite(entry.days_stalled)
          ? entry.days_stalled
          : 0,
    })),
  };
}

export async function fetchStallAlerts(): Promise<StallAlert[]> {
  const response = (await fetchJson<StallAlert[]>("/api/pm/stalls")) ?? [];
  return response.map((entry) => ({
    project_id: Number(entry.project_id) || 0,
    project_name: asString(entry.project_name),
    task_id: Number(entry.task_id) || 0,
    task_name: asString(entry.task_name),
    phase: asString(entry.phase),
    days_stalled: Number(entry.days_stalled) || 0,
  }));
}

export async function fetchProjects(): Promise<ProjectListItem[]> {
  const response = (await fetchJson<ApiProjectListItem[]>("/api/pm/projects")) ?? [];
  return response.map((project) => normalizeProjectListItem(project));
}

export async function fetchProject(projectId: number): Promise<ProjectDetail | null> {
  const response = await fetchJson<ApiProjectDetail>(`/api/pm/projects/${projectId}`, undefined, true);
  if (!response) {
    return null;
  }
  return normalizeProjectDetail(response);
}

export async function createProject(data: ProjectCreateRequest): Promise<ProjectDetail> {
  const response = await fetchJson<ApiProjectDetail>("/api/pm/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!response) {
    throw new Error("Failed to create project.");
  }
  return normalizeProjectDetail(response);
}

export async function updateProjectRecord(
  projectId: number,
  data: Partial<ProjectCreateRequest> & {
    status?: string;
    risk_level?: string;
    actual_end_date?: string | null;
  }
): Promise<ProjectDetail> {
  const response = await fetchJson<ApiProjectDetail>(`/api/pm/projects/${projectId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  if (!response) {
    throw new Error("Failed to update project.");
  }
  return normalizeProjectDetail(response);
}

export async function deleteProjectRecord(projectId: number): Promise<void> {
  await fetchJson(`/api/pm/projects/${projectId}`, { method: "DELETE" });
}

export async function updateTaskStatus(
  taskId: number,
  status: TaskStatus,
  notes?: string
): Promise<void> {
  await fetchJson(`/api/pm/tasks/${taskId}/status`, {
    method: "PUT",
    body: JSON.stringify({
      status,
      notes,
    }),
  });
}

export async function uploadGanttPdf(projectId: number, file: File): Promise<void> {
  const body = new FormData();
  body.append("file", file);
  await fetchJson(`/api/pm/projects/${projectId}/gantt-upload`, {
    method: "POST",
    body,
  });
}

export async function fetchPmInsights(projectId?: number): Promise<ProjectInsight[]> {
  const path = typeof projectId === "number" ? `/api/pm/projects/${projectId}/insights` : "/api/pm/insights";
  const response = (await fetchJson<ApiInsight[]>(path)) ?? [];
  return response.map((insight) => normalizeProjectInsight(insight));
}

export async function fetchShippingPrefill(
  quoteId: number
): Promise<ShippingDocumentState> {
  const response = await fetchJson<ApiShippingEnvelope>(`/api/shipping/${quoteId}/prefill`);
  if (!response) {
    throw new Error("Shipping prefill not available.");
  }
  return normalizeShippingState(response.shipping_data, response.quote_id, response.quote_ref);
}

export async function loadShippingState(
  quoteId: number
): Promise<ShippingLoadResult | null> {
  const response = await fetchJson<ApiShippingLoadEnvelope>(
    `/api/shipping/${quoteId}/load`,
    undefined,
    true
  );
  if (!response) {
    return null;
  }
  return {
    quoteId: response.quote_id,
    quoteRef: response.quote_ref,
    createdDate: response.created_date ?? null,
    modifiedDate: response.modified_date ?? null,
    shippingData: normalizeShippingState(
      response.shipping_data,
      response.quote_id,
      response.quote_ref
    ),
  };
}

export async function saveShippingState(
  quoteId: number,
  shippingData: ShippingDocumentState
): Promise<ShippingSaveResult> {
  const response = await fetchJson<ApiShippingSaveEnvelope>(
    `/api/shipping/${quoteId}/save`,
    {
      method: "POST",
      body: JSON.stringify({
        shipping_data: shippingData,
      }),
    }
  );
  if (!response) {
    throw new Error("Failed to save shipping state.");
  }
  return {
    quoteId: response.quote_id,
    quoteRef: response.quote_ref,
    savedAt: response.saved_at,
    shippingData: normalizeShippingState(
      response.shipping_data,
      response.quote_id,
      response.quote_ref
    ),
  };
}

export async function generateShippingDocs(
  quoteId: number,
  options?: {
    documentType?: ShippingDocumentType;
    outputFormat?: ShippingOutputFormat;
    shippingData?: ShippingDocumentState;
  }
): Promise<{ blob: Blob; filename: string; contentType: string }> {
  const documentType = options?.documentType ?? "all";
  const outputFormat = options?.outputFormat ?? "html";
  const response = await fetch(`${API_BASE}/api/shipping/${quoteId}/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
    body: JSON.stringify({
      document_type: documentType,
      output_format: outputFormat,
      shipping_data: options?.shippingData,
    }),
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) {
        detail = body.detail;
      }
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }

  const contentType = response.headers.get("content-type") ?? "application/octet-stream";
  const disposition = response.headers.get("content-disposition") ?? "";
  const filenameMatch = disposition.match(/filename\*?=(?:UTF-8''|\"?)([^\";]+)/i);
  const rawFilename = filenameMatch?.[1]
    ? decodeURIComponent(filenameMatch[1].replace(/\"/g, "").trim())
    : "";
  const filename = normalizeShippingDownloadFilename(rawFilename, documentType, contentType, outputFormat);

  return {
    blob: await response.blob(),
    filename,
    contentType,
  };
}

export async function fetchCorPrefill(
  quoteId: number
): Promise<CorDocumentState> {
  const response = await fetchJson<ApiCorEnvelope>(`/api/cor/${quoteId}/prefill`);
  if (!response) {
    throw new Error("COR prefill not available.");
  }
  return normalizeCorState(response.cor_data, response.quote_id, response.quote_ref);
}

export async function fetchCorRevisions(
  quoteId: number
): Promise<CorRevisionListResult> {
  const response = await fetchJson<ApiCorRevisionListEnvelope>(`/api/cor/${quoteId}/revisions`);
  if (!response) {
    throw new Error("Failed to load COR revisions.");
  }
  return {
    quoteId: response.quote_id,
    quoteRef: response.quote_ref,
    revisions: (response.revisions ?? [])
      .map((entry) => ({
        corDocumentId:
          typeof entry.cor_document_id === "number" && Number.isFinite(entry.cor_document_id)
            ? entry.cor_document_id
            : 0,
        corNo: asString(entry.cor_no),
        description: asString(entry.description),
        createdDate: entry.created_date ?? null,
        modifiedDate: entry.modified_date ?? null,
      }))
      .filter((entry) => entry.corDocumentId > 0),
  };
}

export async function loadCorState(
  quoteId: number,
  corDocumentId?: number | null
): Promise<CorLoadResult | null> {
  const query = typeof corDocumentId === "number" && Number.isFinite(corDocumentId)
    ? `?cor_document_id=${encodeURIComponent(String(corDocumentId))}`
    : "";
  const response = await fetchJson<ApiCorLoadEnvelope>(
    `/api/cor/${quoteId}/load${query}`,
    undefined,
    true
  );
  if (!response) {
    return null;
  }
  const normalized = normalizeCorState(response.cor_data, response.quote_id, response.quote_ref);
  const corNo = asString(response.cor_no) || normalized.corNo;
  const description = asString(response.description) || normalized.revisionDescription;
  return {
    quoteId: response.quote_id,
    quoteRef: response.quote_ref,
    corDocumentId: response.cor_document_id,
    corNo,
    description,
    createdDate: response.created_date ?? null,
    modifiedDate: response.modified_date ?? null,
    corData: {
      ...normalized,
      corNo,
      revisionDescription: description,
    },
  };
}

export async function saveCorState(
  quoteId: number,
  corData: CorDocumentState,
  options?: {
    corDocumentId?: number | null;
    createNew?: boolean;
  }
): Promise<CorSaveResult> {
  const response = await fetchJson<ApiCorSaveEnvelope>(
    `/api/cor/${quoteId}/save`,
    {
      method: "POST",
      body: JSON.stringify({
        cor_data: corData,
        cor_document_id:
          typeof options?.corDocumentId === "number" && Number.isFinite(options.corDocumentId)
            ? options.corDocumentId
            : null,
        create_new: Boolean(options?.createNew),
        cor_no: corData.corNo,
        description: corData.revisionDescription,
      }),
    }
  );
  if (!response) {
    throw new Error("Failed to save COR state.");
  }
  const normalized = normalizeCorState(response.cor_data, response.quote_id, response.quote_ref);
  const corNo = asString(response.cor_no) || normalized.corNo;
  const description = asString(response.description) || normalized.revisionDescription;
  return {
    quoteId: response.quote_id,
    quoteRef: response.quote_ref,
    corDocumentId: response.cor_document_id,
    corNo,
    description,
    savedAt: response.saved_at,
    corData: {
      ...normalized,
      corNo,
      revisionDescription: description,
    },
  };
}

export async function generateCorDoc(
  quoteId: number,
  options?: {
    corData?: CorDocumentState;
    corDocumentId?: number | null;
  }
): Promise<{ blob: Blob; filename: string; contentType: string }> {
  const response = await fetch(`${API_BASE}/api/cor/${quoteId}/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
    body: JSON.stringify({
      cor_data: options?.corData,
      cor_document_id:
        typeof options?.corDocumentId === "number" && Number.isFinite(options.corDocumentId)
          ? options.corDocumentId
          : null,
    }),
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) {
        detail = body.detail;
      }
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }

  const contentType = response.headers.get("content-type") ?? "application/octet-stream";
  const disposition = response.headers.get("content-disposition") ?? "";
  const filenameMatch = disposition.match(/filename\*?=(?:UTF-8''|\"?)([^\";]+)/i);
  const rawFilename = filenameMatch?.[1]
    ? decodeURIComponent(filenameMatch[1].replace(/\"/g, "").trim())
    : "";
  const filename = normalizeCorDownloadFilename(rawFilename, contentType);

  return {
    blob: await response.blob(),
    filename,
    contentType,
  };
}

export async function updateQuoteClientInfo(
  quoteId: number,
  clientInfo: QuoteDetail["clientInfo"]
): Promise<void> {
  await fetchJson(`/api/quotes/${quoteId}`, {
    method: "PUT",
    body: JSON.stringify({
      ax: clientInfo.ax,
      customer_name: clientInfo.customerName,
      company: clientInfo.company,
      machine_model: clientInfo.machine,
      serial_number: clientInfo.serialNumber,
      customer_contact_person: clientInfo.clientContact,
      telephone: clientInfo.telephone,
      sold_to_address: joinAddressLines(
        clientInfo.soldToAddress1,
        clientInfo.soldToAddress2,
        clientInfo.soldToAddress3
      ),
      ship_to_address: joinAddressLines(
        clientInfo.shipToAddress1,
        clientInfo.shipToAddress2,
        clientInfo.shipToAddress3
      ),
      customer_po: clientInfo.customerPO,
      order_date: clientInfo.orderDate,
      ox: clientInfo.ox,
      via: clientInfo.via,
      incoterm: clientInfo.incoterm,
      tax_id: clientInfo.taxId,
      hs_code: clientInfo.hsCode,
      customer_number: clientInfo.customerNumber,
    }),
  });
}

export async function saveMachineTemplate(
  machineId: number,
  fields: Record<string, { value: string; confidence: number }>
): Promise<void> {
  const payload: Record<string, string> = {};
  for (const [key, value] of Object.entries(fields)) {
    payload[key] = value.value;
  }
  await fetchJson(`/api/machines/${machineId}/template`, {
    method: "PUT",
    body: JSON.stringify({
      template_type: "GOA",
      template_data: payload,
    }),
  });
}

export async function uploadQuotePdf(
  file: File,
  existingClientId?: number
): Promise<{ quote_ref: string; items_count: number }> {
  const body = new FormData();
  body.append("file", file);
  if (typeof existingClientId === "number") {
    body.append("existing_client_id", String(existingClientId));
  }

  const response = await fetchJson<{ quote_ref: string; items_count: number }>(
    "/api/quotes/upload",
    {
      method: "POST",
      body,
    }
  );
  if (!response) {
    throw new Error("Upload failed.");
  }
  return response;
}

export async function fetchProcessingArtifacts(quoteRef: string): Promise<ProcessingArtifacts> {
  const response = await fetchJson<ApiQuoteArtifacts>(
    `/api/processing/artifacts/${encodeURIComponent(quoteRef)}`
  );
  if (!response) {
    throw new Error("Quote artifacts not found.");
  }

  const machineList: MachineData[] = [];
  const commonItemsMap = new Map<string, LineItem>();
  for (const machine of response.machines) {
    const machineData = machine.machine_data as Record<string, unknown> | undefined;
    if (!machineData) continue;
    const mainItemRaw = (machineData.main_item as Record<string, unknown> | undefined) ?? {};
    const addOnsRaw = (machineData.add_ons as Array<Record<string, unknown>> | undefined) ?? [];
    const commonItemsRaw =
      (machineData.common_items as Array<Record<string, unknown>> | undefined) ?? [];

    for (const item of commonItemsRaw) {
      const normalized = normalizeItem(item);
      const key = [
        normalized.description.trim(),
        normalized.quantity_text.trim(),
        normalized.selection_text.trim(),
        normalized.item_price_numeric == null ? "" : String(normalized.item_price_numeric),
      ].join("|");
      if (!normalized.description.trim() || commonItemsMap.has(key)) continue;
      commonItemsMap.set(key, normalized);
    }

    machineList.push({
      id: typeof machine.id === "number" ? machine.id : undefined,
      machine_name: String(machineData.machine_name ?? machine.machine_name ?? "Machine"),
      main_item: normalizeItem(mainItemRaw),
      add_ons: addOnsRaw.map((addon) => normalizeItem(addon)),
    });
  }

  return {
    quoteRef: response.quote_ref,
    fullPdfText: response.full_pdf_text ?? "",
    pdfFilename: response.pdf_filename ?? "",
    items: response.items.map(normalizeItem),
    machines: machineList,
    commonItems: Array.from(commonItemsMap.values()),
  };
}

export async function identifyProcessingMachines(items: LineItem[]): Promise<{
  machines: MachineData[];
  common_items: LineItem[];
}> {
  const response = await fetchJson<{ machines: MachineData[]; common_items: LineItem[] }>(
    "/api/processing/identify",
    {
      method: "POST",
      body: JSON.stringify({ items }),
    }
  );
  if (!response) {
    throw new Error("Machine identification failed.");
  }
  return response;
}

export async function groupProcessingItems(
  allItems: LineItem[],
  mainMachineIndices: number[],
  commonOptionIndices: number[],
  quoteRef?: string
): Promise<{ machines: MachineData[]; common_items: LineItem[] }> {
  const response = await fetchJson<{ machines: MachineData[]; common_items: LineItem[] }>(
    "/api/processing/group",
    {
      method: "POST",
      body: JSON.stringify({
        quote_ref: quoteRef,
        all_items: allItems,
        main_machine_indices: mainMachineIndices,
        common_option_indices: commonOptionIndices,
      }),
    }
  );
  if (!response) {
    throw new Error("Item grouping failed.");
  }
  return response;
}

export async function fetchProcessingMachineData(machineId: number): Promise<{
  quoteRef: string;
  machine: MachineData;
  commonItems: LineItem[];
  fullPdfText: string;
}> {
  const response = await fetchJson<ApiMachineProcessingData>(
    `/api/processing/machine-data/${machineId}`
  );
  if (!response) {
    throw new Error("Machine data not found.");
  }

  const machinePayload = response.machine_data ?? {};
  const mainItemRaw =
    (machinePayload.main_item as Record<string, unknown> | undefined) ??
    response.main_item ??
    {};
  const optionsRaw =
    (machinePayload.add_ons as Array<Record<string, unknown>> | undefined) ??
    response.options ??
    [];
  const commonRaw =
    (machinePayload.common_items as Array<Record<string, unknown>> | undefined) ??
    response.common_items ??
    [];

  return {
    quoteRef: response.quote_ref,
    machine: {
      id: typeof response.machine_id === "number" ? response.machine_id : undefined,
      machine_name: String(machinePayload.machine_name ?? "Machine"),
      main_item: normalizeItem(mainItemRaw),
      add_ons: optionsRaw.map((entry) => normalizeItem(entry)),
    },
    commonItems: commonRaw.map((entry) => normalizeItem(entry)),
    fullPdfText: response.full_pdf_text ?? "",
  };
}

export async function extractMachineFields(input: {
  machine_data: MachineData;
  common_items: LineItem[];
  full_pdf_text: string;
  template_contexts?: Record<string, unknown> | null;
}): Promise<ExtractionResult> {
  const response = await fetchJson<ExtractionResult>("/api/processing/extract", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!response) {
    throw new Error("Extraction failed.");
  }
  return response;
}

export async function generateMachineDocument(input: {
  machine_data: MachineData;
  filled_data: Record<string, string>;
  common_items: LineItem[];
  template_contexts?: Record<string, unknown> | null;
  machine_id?: number | null;
}): Promise<GeneratedDocumentResult> {
  const response = await fetchJson<GeneratedDocumentResult>("/api/processing/generate", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!response) {
    throw new Error("Document generation failed.");
  }
  return response;
}

export async function fillGoaForm(
  filledData: Record<string, string>,
  outputOptions?: GoaOutputOptions
): Promise<{ html: string }> {
  const response = await fetchJson<{ html: string }>("/api/processing/fill-form", {
    method: "POST",
    body: JSON.stringify({
      filled_data: filledData,
      output_options: outputOptions
        ? {
            included_sections: outputOptions.includedSections,
            hide_empty_sections: outputOptions.hideEmptySections,
            hide_empty_fields: outputOptions.hideEmptyFields,
            pure_output: outputOptions.pureOutput,
            label_overrides: outputOptions.labelOverrides,
            format: outputOptions.format,
          }
        : undefined,
    }),
  });
  if (!response) {
    throw new Error("Failed to render GOA form.");
  }
  return response;
}

export async function fetchGoaFormSchema(): Promise<GoaFormSchemaResponse> {
  const response = await fetchJson<ApiGoaFormSchemaResponse>("/api/processing/goa-schema");
  if (!response) {
    throw new Error("Failed to load GOA form schema.");
  }

  return {
    sections: (response.sections ?? []).map((section) => ({
      id: section.id || section.title.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "section",
      title: section.title,
      fieldCount: typeof section.field_count === "number" ? section.field_count : 0,
      groups: section.groups ?? [],
    })),
    fieldCount: typeof response.field_count === "number" ? response.field_count : 0,
  };
}

export async function listGoaForms(filters?: {
  quoteRef?: string;
  machineId?: number;
}): Promise<GoaFormListItem[]> {
  const params = new URLSearchParams();
  if (filters?.quoteRef) params.set("quote_ref", filters.quoteRef);
  if (typeof filters?.machineId === "number") params.set("machine_id", String(filters.machineId));

  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = (await fetchJson<ApiGoaFormListItem[]>(`/api/processing/goa-forms${suffix}`)) ?? [];

  return response.map((row) => ({
    machineTemplateId: row.machine_template_id,
    machineId: row.machine_id,
    quoteRef: row.quote_ref,
    machineName: row.machine_name,
    templateType: row.template_type,
    generatedFilePath: row.generated_file_path ?? null,
    processingDate: row.processing_date ?? null,
  }));
}

export async function fetchGoaForm(machineTemplateId: number): Promise<GoaFormDetail> {
  const response = await fetchJson<ApiGoaFormDetail>(`/api/processing/goa-form/${machineTemplateId}`);
  if (!response) {
    throw new Error("GOA form not found.");
  }

  const templateData: Record<string, string> = {};
  for (const [key, value] of Object.entries(response.template_data ?? {})) {
    templateData[key] = value == null ? "" : String(value);
  }

  const outputOptions: GoaOutputOptions | null = response.output_options
    ? {
        includedSections: response.output_options.included_sections ?? undefined,
        hideEmptySections:
          typeof response.output_options.hide_empty_sections === "boolean"
            ? response.output_options.hide_empty_sections
            : undefined,
        hideEmptyFields:
          typeof response.output_options.hide_empty_fields === "boolean"
            ? response.output_options.hide_empty_fields
            : undefined,
        pureOutput:
          typeof response.output_options.pure_output === "boolean"
            ? response.output_options.pure_output
            : undefined,
        labelOverrides: response.output_options.label_overrides ?? undefined,
        format: response.output_options.format ?? undefined,
      }
    : null;

  return {
    machineTemplateId: response.machine_template_id,
    machineId: response.machine_id,
    quoteRef: response.quote_ref,
    machineName: response.machine_name,
    templateType: response.template_type,
    generatedFilePath: response.generated_file_path ?? null,
    processingDate: response.processing_date ?? null,
    templateData,
    outputOptions,
    fieldLabels: response.field_labels ?? {},
    modifications: response.modifications ?? [],
    html: response.html,
  };
}

export async function upsertMachineTemplateData(
  machineId: number,
  templateData: Record<string, string>
): Promise<{ templateId: number; generatedFilePath: string | null }> {
  const response = await fetchJson<ApiTemplateResponse>(`/api/machines/${machineId}/template`, {
    method: "PUT",
    body: JSON.stringify({
      template_type: "GOA",
      template_data: templateData,
    }),
  });

  if (!response) {
    throw new Error("Failed to save machine template data.");
  }

  return {
    templateId: response.id,
    generatedFilePath: response.generated_file_path ?? null,
  };
}

export async function saveGoaForm(input: {
  machineTemplateId: number;
  filledData: Record<string, string>;
  generateOutput?: boolean;
  outputOptions?: GoaOutputOptions;
  modifications?: Array<{
    field_key: string;
    original_value?: string;
    modified_value: string;
    reason?: string;
  }>;
}): Promise<GoaFormSaveResult> {
  const response = await fetchJson<ApiGoaFormSaveResponse>(
    `/api/processing/goa-form/${input.machineTemplateId}`,
    {
      method: "PUT",
      body: JSON.stringify({
        filled_data: input.filledData,
        generate_output: input.generateOutput ?? true,
        output_options: input.outputOptions
          ? {
              included_sections: input.outputOptions.includedSections,
              hide_empty_sections: input.outputOptions.hideEmptySections,
              hide_empty_fields: input.outputOptions.hideEmptyFields,
              pure_output: input.outputOptions.pureOutput,
              label_overrides: input.outputOptions.labelOverrides,
              format: input.outputOptions.format,
            }
          : undefined,
        modifications: input.modifications,
      }),
    }
  );

  if (!response) {
    throw new Error("Failed to save GOA form.");
  }

  return {
    machineTemplateId: response.machine_template_id,
    savedAt: response.saved_at,
    filePath: response.file_path,
    html: response.html,
  };
}

export async function generateGoaDocument(
  machineTemplateId: number,
  outputOptions?: GoaOutputOptions
): Promise<GoaFormSaveResult> {
  const response = await fetchJson<ApiGoaFormSaveResponse>(
    `/api/processing/goa-form/${machineTemplateId}/generate-document`,
    {
      method: "POST",
      body: outputOptions
        ? JSON.stringify({
            output_options: {
              included_sections: outputOptions.includedSections,
              hide_empty_sections: outputOptions.hideEmptySections,
              hide_empty_fields: outputOptions.hideEmptyFields,
              pure_output: outputOptions.pureOutput,
              label_overrides: outputOptions.labelOverrides,
              format: outputOptions.format,
            } satisfies ApiGoaOutputOptions,
          })
        : undefined,
    }
  );

  if (!response) {
    throw new Error("Failed to generate GOA document.");
  }

  return {
    machineTemplateId: response.machine_template_id,
    savedAt: response.saved_at,
    filePath: response.file_path,
    html: response.html,
  };
}

export async function generateDocumentWithOptions(input: {
  machineTemplateId: number;
  filledData: Record<string, string>;
  options?: GoaOutputOptions;
}): Promise<GoaGeneratedDocumentResult> {
  const response = await fetchJson<ApiGoaGenerateDocumentResponse>("/api/generate-document", {
    method: "POST",
    body: JSON.stringify({
      machine_template_id: input.machineTemplateId,
      filled_data: input.filledData,
      options: input.options
        ? {
            included_sections: input.options.includedSections,
            hide_empty_sections: input.options.hideEmptySections,
            hide_empty_fields: input.options.hideEmptyFields,
            pure_output: input.options.pureOutput,
            label_overrides: input.options.labelOverrides,
            format: input.options.format,
          }
        : undefined,
    }),
  });

  if (!response) {
    throw new Error("Failed to generate document.");
  }

  const downloadUrl = response.download_url.startsWith("http")
    ? response.download_url
    : `${API_BASE}${response.download_url}`;

  return {
    machineTemplateId: response.machine_template_id,
    generatedAt: response.generated_at,
    format: response.format,
    filePath: response.file_path,
    downloadUrl,
  };
}

export function getGoaFormFileUrl(machineTemplateId: number): string {
  return `${API_BASE}/api/processing/goa-form/${machineTemplateId}/file`;
}

export async function fetchMachineReport(machineId: number): Promise<ApiReportResponse> {
  const response = await fetchJson<ApiReportResponse>(`/api/reports/${machineId}`);
  if (!response) {
    throw new Error("Report not found.");
  }
  return response;
}

export async function fetchMachineSummaryReport(
  machineId: number
): Promise<ApiReportResponse> {
  const response = await fetchJson<ApiReportResponse>(`/api/reports/${machineId}/summary`);
  if (!response) {
    throw new Error("Summary report not found.");
  }
  return response;
}
