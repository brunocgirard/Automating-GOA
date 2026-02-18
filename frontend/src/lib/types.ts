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
