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

export function ItemsTable({ items }: ItemsTableProps) {
  const total = items.reduce((sum, i) => sum + (i.price ?? 0), 0);

  return (
    <div className="rounded-md border">
      <Table className="min-w-[720px]">
        <TableHeader>
          <TableRow>
            <TableHead>Description</TableHead>
            <TableHead className="w-24 text-center">Qty</TableHead>
            <TableHead className="w-28">Selection</TableHead>
            <TableHead className="w-32 text-right">Price</TableHead>
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
                  ? `EUR ${item.price.toLocaleString()}`
                  : "-"}
              </TableCell>
            </TableRow>
          ))}
          <TableRow className="font-semibold">
            <TableCell colSpan={3}>Total</TableCell>
            <TableCell className="text-right">
              EUR {total.toLocaleString()}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
