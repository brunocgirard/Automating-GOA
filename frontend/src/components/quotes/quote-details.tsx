"use client";

import { Input } from "@/components/ui/input";
import type { QuoteDetail } from "@/lib/api";

interface QuoteDetailsProps {
  clientInfo: QuoteDetail["clientInfo"];
  onChange: (key: keyof QuoteDetail["clientInfo"], value: string) => void;
}

const fields: Array<{
  key: keyof QuoteDetail["clientInfo"];
  label: string;
  readOnly?: boolean;
}> = [
  { key: "quoteNo", label: "Quote No", readOnly: true },
  { key: "ax", label: "Ax" },
  { key: "customerName", label: "Customer" },
  { key: "company", label: "Company" },
  { key: "machine", label: "Machine" },
  { key: "serialNumber", label: "Serial Number" },
  { key: "soldToAddress1", label: "Sold to/Address 1" },
  { key: "soldToAddress2", label: "Sold to/Address 2" },
  { key: "soldToAddress3", label: "Sold to/Address 3" },
  { key: "shipToAddress1", label: "Ship to/Address 1" },
  { key: "shipToAddress2", label: "Ship to/Address 2" },
  { key: "shipToAddress3", label: "Ship to/Address 3" },
  { key: "telephone", label: "Telefone" },
  { key: "customerPO", label: "Customer PO" },
  { key: "orderDate", label: "Order date" },
  { key: "ox", label: "Ox" },
  { key: "via", label: "Via" },
  { key: "incoterm", label: "Incoterm" },
  { key: "taxId", label: "Tax ID" },
  { key: "hsCode", label: "H.S" },
  { key: "customerNumber", label: "Customer Number" },
  { key: "clientContact", label: "Client Contact" },
];

export function QuoteClientInfo({ clientInfo, onChange }: QuoteDetailsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {fields.map((field) => (
          <div key={field.key} className="space-y-1">
            <label className="text-sm font-medium">{field.label}</label>
            <Input
              value={clientInfo[field.key]}
              readOnly={field.readOnly}
              disabled={field.readOnly}
              onChange={(e) => onChange(field.key, e.target.value)}
            />
          </div>
      ))}
    </div>
  );
}
