export interface Quote {
  id: number;
  quote_ref: string;
  customer_name: string;
  machine_model: string | null;
  country_destination: string | null;
  sold_to_address: string | null;
  ship_to_address: string | null;
  telephone: string | null;
  customer_contact_person: string | null;
  customer_po: string | null;
  processing_date: string | null;
}

export interface Machine {
  id: number;
  machine_name: string;
  quote_ref: string;
  client_name: string;
  client_id: number;
  status: 'draft' | 'processed' | 'ready';
  processing_date: string | null;
  template_data: Record<string, string> | null;
}

export interface LineItem {
  id?: number;
  description: string;
  quantity_text: string;
  selection_text: string;
  item_price_numeric: number | null;
}

export interface MachineGrouping {
  machines: MachineData[];
  common_items: LineItem[];
}

export interface MachineData {
  id?: number;
  machine_name: string;
  main_item: LineItem;
  add_ons: LineItem[];
}

export interface ExtractionResult {
  filled_data: Record<string, string>;
  confidence_scores: Record<string, number>;
  suggestions: Array<Record<string, unknown>>;
  metadata?: {
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
  } | null;
}

export type ProcessingStep =
  | "load-quote"
  | "select-machine"
  | "process-machine";

export type ProjectPhase =
  | "sales_onboarding"
  | "engineering_prep"
  | "design_approval"
  | "production"
  | "delivery";

export type TaskStatus = "pending" | "in_progress" | "done" | "skipped";
export type RiskLevel = "on_track" | "at_risk" | "overdue";

export interface ProjectTask {
  id: number;
  project_id: number;
  task_name: string;
  task_order: number;
  phase: ProjectPhase;
  status: TaskStatus;
  planned_date: string | null;
  actual_date: string | null;
  notes: string | null;
  modified_date: string | null;
}

export interface ProjectListItem {
  id: number;
  project_name: string;
  customer_name: string;
  quote_ref: string | null;
  machine_summary: string | null;
  status: string;
  risk_level: RiskLevel;
  current_phase: ProjectPhase | null;
  current_task: string | null;
  days_in_phase: number | null;
  progress_pct: number;
  start_date: string | null;
  target_end_date: string | null;
  actual_end_date: string | null;
  created_date: string | null;
  modified_date: string | null;
}

export interface ProjectDetail extends ProjectListItem {
  tasks: ProjectTask[];
  gantt_data: Record<string, unknown> | null;
}

export interface ProjectCreateRequest {
  project_name: string;
  customer_name: string;
  quote_ref?: string | null;
  machine_summary?: string | null;
  start_date?: string | null;
  target_end_date?: string | null;
}

export interface AtRiskSummary {
  count: number;
  projects: Array<{
    project_id?: number | null;
    name: string;
    task: string;
    phase: string;
    days_stalled: number;
  }>;
}

export interface StallAlert {
  project_id: number;
  project_name: string;
  task_id: number;
  task_name: string;
  phase: string;
  days_stalled: number;
}

export interface ProjectInsight {
  project_id: number | null;
  project_name: string | null;
  task_id: number | null;
  task_name: string | null;
  type: string;
  severity: "critical" | "warning" | "info";
  title: string;
  message: string;
  phase: string | null;
  days_stalled: number | null;
}
