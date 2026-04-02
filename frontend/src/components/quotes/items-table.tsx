import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface ItemsTableProps {
  items: {
    description: string;
    quantity: string;
    selection: string;
    price: number | null;
  }[];
}

const DEFAULT_CURRENCY = "USD";

function detectCurrencyFromText(value: string): string | null {
  const text = value.trim();
  if (!text) return null;

  const upper = text.toUpperCase();

  if (text.includes("€") || /\bEUR\b/.test(upper)) return "EUR";
  if (/\bCAD\b/.test(upper) || /(?:^|[^A-Z])(?:C\$|CA\$)/.test(upper)) return "CAD";
  if (text.includes("£") || /\bGBP\b/.test(upper)) return "GBP";
  if (/\bUSD\b/.test(upper) || /\bUS\$/.test(upper) || text.includes("$")) return "USD";

  return null;
}

function inferQuoteCurrency(
  items: {
    selection: string;
    price: number | null;
  }[]
): string {
  const counts = new Map<string, number>();

  for (const item of items) {
    if (item.price == null) continue;
    const currency = detectCurrencyFromText(item.selection);
    if (!currency) continue;
    counts.set(currency, (counts.get(currency) ?? 0) + 1);
  }

  let selected = DEFAULT_CURRENCY;
  let selectedCount = 0;
  for (const [currency, count] of counts.entries()) {
    if (count > selectedCount) {
      selected = currency;
      selectedCount = count;
    }
  }

  return selected;
}

function formatCurrencyAmount(value: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
}

export function ItemsTable({ items }: ItemsTableProps) {
  const quoteCurrency = inferQuoteCurrency(items);
  const total = items.reduce((sum, i) => sum + (i.price ?? 0), 0);

  return (
    <div className="rounded-md border">
      <Table className="min-w-[720px]">
        <TableHeader>
          <TableRow>
            <TableHead>Description</TableHead>
            <TableHead className="w-24 text-center">Qty</TableHead>
            <TableHead className="w-28">Selection</TableHead>
            <TableHead className="w-32 text-right">{`Price (${quoteCurrency})`}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item, i) => (
            <TableRow key={i}>
              <TableCell className="whitespace-normal">{item.description}</TableCell>
              <TableCell className="text-center">{item.quantity}</TableCell>
              <TableCell>{item.selection}</TableCell>
              <TableCell className="text-right">
                {item.price != null
                  ? formatCurrencyAmount(item.price, detectCurrencyFromText(item.selection) ?? quoteCurrency)
                  : "-"}
              </TableCell>
            </TableRow>
          ))}
          <TableRow className="font-semibold">
            <TableCell colSpan={3}>Total</TableCell>
            <TableCell className="text-right">
              {formatCurrencyAmount(total, quoteCurrency)}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
