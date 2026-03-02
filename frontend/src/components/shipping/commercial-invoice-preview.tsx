import type { ShippingDocumentState } from "@/lib/api";
import { line, toNumber } from "@/lib/doc-utils";

interface CommercialInvoicePreviewProps {
  state: ShippingDocumentState;
}

const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function CommercialInvoicePreview({ state }: CommercialInvoicePreviewProps) {
  const { client, machines, meta } = state;
  const manualTotal = toNumber(meta.totalInvoiceAmount);
  const computedTotal = machines.reduce((sum, machine) => sum + machine.unitPrice, 0);
  const total = manualTotal > 0 ? manualTotal : computedTotal;

  return (
    <div className="rounded-lg border bg-white p-4 text-black shadow-sm">
      <div className="mb-4 border-b pb-3">
        <h3 className="text-lg font-semibold">Commercial Invoice</h3>
        <p className="text-xs text-neutral-500">Quote: {state.quoteRef || "-"} | Currency: USD</p>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border p-3">
          <p className="mb-1 text-xs font-semibold uppercase text-neutral-500">Sold To</p>
          <p className="text-sm">{line(client.customerName || client.company)}</p>
          <p className="text-sm">{line(client.soldToAddress1)}</p>
          <p className="text-sm">{line(client.soldToAddress2)}</p>
          <p className="text-sm whitespace-pre-line">{line(client.soldToAddress3)}</p>
          <p className="mt-1 text-sm">Tax ID: {line(client.taxId)}</p>
        </div>
        <div className="rounded-md border p-3">
          <p className="mb-1 text-xs font-semibold uppercase text-neutral-500">Ship To</p>
          <p className="text-sm">{line(client.customerName || client.company)}</p>
          <p className="text-sm">{line(client.shipToAddress1)}</p>
          <p className="text-sm">{line(client.shipToAddress2)}</p>
          <p className="text-sm whitespace-pre-line">{line(client.shipToAddress3)}</p>
        </div>
      </div>

      <div className="mb-4 overflow-hidden rounded-md border">
        <table className="w-full border-collapse text-sm">
          <tbody>
            <tr className="border-b">
              <td className="p-2 font-medium">Customer PO</td>
              <td className="p-2">{line(client.customerPO)}</td>
              <td className="p-2 font-medium">Order date</td>
              <td className="p-2">{line(client.orderDate)}</td>
            </tr>
            <tr className="border-b">
              <td className="p-2 font-medium">Order number</td>
              <td className="p-2">{line(client.ox)}</td>
              <td className="p-2 font-medium">Broker</td>
              <td className="p-2">{line(meta.brokerInfo)}</td>
            </tr>
            <tr>
              <td className="p-2 font-medium">Incoterm</td>
              <td className="p-2">{line(client.incoterm)}</td>
              <td className="p-2 font-medium">Invoice total</td>
              <td className="p-2">{usd.format(total)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="overflow-hidden rounded-md border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-neutral-50 text-left">
              <th className="p-2 font-medium">Qty</th>
              <th className="p-2 font-medium">Description</th>
              <th className="p-2 text-right font-medium">Unit (USD)</th>
              <th className="p-2 text-right font-medium">Total (USD)</th>
            </tr>
          </thead>
          <tbody>
            {machines.length === 0 ? (
              <tr>
                <td className="p-3 text-center text-neutral-500" colSpan={4}>
                  No machines configured.
                </td>
              </tr>
            ) : (
              machines.map((machine) => (
                <tr key={machine.id} className="border-t">
                  <td className="p-2">1</td>
                  <td className="p-2">
                    <p>{line(machine.model || machine.machineName)}</p>
                    <p className="text-xs text-neutral-600">Serial: {line(machine.serialNumber)}</p>
                    <p className="text-xs text-neutral-600">HS: {line(machine.hsCode)}</p>
                  </td>
                  <td className="p-2 text-right">{usd.format(machine.unitPrice)}</td>
                  <td className="p-2 text-right">{usd.format(machine.unitPrice)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 ml-auto max-w-xs rounded-md border p-3 text-sm">
        <div className="flex items-center justify-between">
          <span>Amount before tax</span>
          <span>{usd.format(total)}</span>
        </div>
        <div className="mt-1 flex items-center justify-between font-semibold">
          <span>Total amount (USD)</span>
          <span>{usd.format(total)}</span>
        </div>
      </div>

      <style jsx>{`
        @media print {
          :global(body) {
            background: #fff !important;
          }
        }
      `}</style>
    </div>
  );
}
