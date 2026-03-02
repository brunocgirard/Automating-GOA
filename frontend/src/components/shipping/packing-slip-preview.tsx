import type { ShippingDocumentState } from "@/lib/api";
import { line, toNumber } from "@/lib/doc-utils";

interface PackingSlipPreviewProps {
  state: ShippingDocumentState;
}

export function PackingSlipPreview({ state }: PackingSlipPreviewProps) {
  const { client, machines, trucks } = state;
  const truckById = new Map(trucks.map((truck) => [truck.id, truck.name]));

  const totalCrates = machines.reduce((sum, machine) => sum + machine.crates.length, 0);
  const totalWeight = machines.reduce(
    (sum, machine) => sum + machine.crates.reduce((crateSum, crate) => crateSum + toNumber(crate.weightLbs), 0),
    0
  );

  return (
    <div className="rounded-lg border bg-white p-4 text-black shadow-sm">
      <div className="mb-4 border-b pb-3">
        <h3 className="text-lg font-semibold">Packing Slip</h3>
        <p className="text-xs text-neutral-500">Quote: {state.quoteRef || "-"}</p>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border p-3">
          <p className="mb-1 text-xs font-semibold uppercase text-neutral-500">Sold To</p>
          <p className="text-sm">{line(client.customerName || client.company)}</p>
          <p className="text-sm">{line(client.soldToAddress1)}</p>
          <p className="text-sm">{line(client.soldToAddress2)}</p>
          <p className="text-sm whitespace-pre-line">{line(client.soldToAddress3)}</p>
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
              <td className="p-2 font-medium">Order Date</td>
              <td className="p-2">{line(client.orderDate)}</td>
            </tr>
            <tr>
              <td className="p-2 font-medium">Incoterm</td>
              <td className="p-2">{line(client.incoterm)}</td>
              <td className="p-2 font-medium">Totals</td>
              <td className="p-2">
                {totalCrates} crates / {totalWeight.toFixed(1)} lbs
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="overflow-hidden rounded-md border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-neutral-50 text-left">
              <th className="p-2 font-medium">Truck</th>
              <th className="p-2 font-medium">Machine</th>
              <th className="p-2 font-medium">Serial</th>
              <th className="p-2 font-medium">HS</th>
              <th className="p-2 text-right font-medium">Crates</th>
            </tr>
          </thead>
          <tbody>
            {machines.length === 0 ? (
              <tr>
                <td className="p-3 text-center text-neutral-500" colSpan={5}>
                  No machines configured.
                </td>
              </tr>
            ) : (
              machines.map((machine) => (
                <tr key={machine.id} className="border-t">
                  <td className="p-2">{line(truckById.get(machine.truckId) ?? "Truck")}</td>
                  <td className="p-2">{line(machine.model || machine.machineName)}</td>
                  <td className="p-2">{line(machine.serialNumber)}</td>
                  <td className="p-2">{line(machine.hsCode)}</td>
                  <td className="p-2 text-right">{machine.crates.length}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
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
