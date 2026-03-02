import type { ShippingDocumentState } from "@/lib/api";
import { line } from "@/lib/doc-utils";

interface CertificateOriginPreviewProps {
  state: ShippingDocumentState;
}

export function CertificateOriginPreview({ state }: CertificateOriginPreviewProps) {
  const { client, machines, meta } = state;

  return (
    <div className="rounded-lg border bg-white p-4 text-black shadow-sm">
      <div className="mb-4 border-b pb-3">
        <h3 className="text-lg font-semibold">Certificate of Origin (USMCA / CUSMA)</h3>
        <p className="text-xs text-neutral-500">Quote: {state.quoteRef || "-"}</p>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border p-3">
          <p className="mb-1 text-xs font-semibold uppercase text-neutral-500">Exporter</p>
          <p className="text-sm">CAPMATIC LTD</p>
          <p className="text-sm">12180 ALBERT-HUDON</p>
          <p className="text-sm">MONTREAL, QUEBEC, CANADA H1G 3K7</p>
          <p className="mt-1 text-sm">Telephone: 514-322-0062</p>
        </div>
        <div className="rounded-md border p-3">
          <p className="mb-1 text-xs font-semibold uppercase text-neutral-500">Importer</p>
          <p className="text-sm">{line(client.customerName || client.company)}</p>
          <p className="text-sm">{line(client.soldToAddress1)}</p>
          <p className="text-sm">{line(client.soldToAddress2)}</p>
          <p className="text-sm whitespace-pre-line">{line(client.soldToAddress3)}</p>
          <p className="mt-1 text-sm">Tax ID: {line(client.taxId)}</p>
        </div>
      </div>

      <div className="mb-4 overflow-hidden rounded-md border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-neutral-50 text-left">
              <th className="p-2 font-medium">Description of goods</th>
              <th className="p-2 font-medium">HS tariff</th>
              <th className="p-2 font-medium">Origin criterion</th>
              <th className="p-2 font-medium">Country of origin</th>
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
                  <td className="p-2">{line(machine.model || machine.machineName)}</td>
                  <td className="p-2">{line(machine.hsCode)}</td>
                  <td className="p-2">{line(meta.originCriterion)}</td>
                  <td className="p-2">{line(meta.countryOfOrigin)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border p-3 text-sm">
          <p className="font-medium">Blanket period</p>
          <p>From: {line(meta.blanketFrom)}</p>
          <p>To: {line(meta.blanketTo)}</p>
        </div>
        <div className="rounded-md border p-3 text-sm">
          <p className="font-medium">Certifier</p>
          <p>{line(meta.certifierName)}</p>
          <p>{line(meta.certifierTitle)}</p>
          <p>{line(meta.certifierDate)}</p>
          <p>{line(meta.certifierContact)}</p>
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
