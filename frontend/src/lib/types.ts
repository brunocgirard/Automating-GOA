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
}

export type ProcessingStep =
  | "load-quote"
  | "select-machine"
  | "process-machine";
