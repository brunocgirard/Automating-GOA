"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Loader2 } from "lucide-react";
import type { LineItem } from "@/lib/types";

interface MachineSelectorProps {
  items: LineItem[];
  onConfirm: (selectedIndices: number[]) => void;
  onAutoIdentify?: () => Promise<number[]>;
  initialSelectedIndices?: number[];
}

export function MachineSelector({
  items,
  onConfirm,
  onAutoIdentify,
  initialSelectedIndices,
}: MachineSelectorProps) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [identifying, setIdentifying] = useState(false);

  useEffect(() => {
    if (!initialSelectedIndices) return;
    setSelected(new Set(initialSelectedIndices));
  }, [initialSelectedIndices]);

  const toggle = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const autoIdentify = async () => {
    setIdentifying(true);
    try {
      if (onAutoIdentify) {
        const indices = await onAutoIdentify();
        setSelected(new Set(indices));
      } else {
        const auto = new Set<number>();
        items.forEach((item, i) => {
          if (
            item.item_price_numeric &&
            item.item_price_numeric > 50000 &&
            item.quantity_text === "1"
          ) {
            auto.add(i);
          }
        });
        setSelected(auto);
      }
    } catch {
      // Keep existing selection when auto-identification fails.
    } finally {
      setIdentifying(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-lg font-semibold">Identify Machines</h3>
        <Button
          variant="outline"
          onClick={autoIdentify}
          disabled={identifying}
          className="w-full sm:w-auto"
        >
          {identifying && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Auto-Identify
        </Button>
      </div>
      <div className="rounded-md border">
        <Table className="min-w-[720px]">
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">Select</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="w-24 text-right">Qty</TableHead>
              <TableHead className="w-32 text-right">Price</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, i) => (
              <TableRow key={i}>
                <TableCell>
                  <Checkbox
                    checked={selected.has(i)}
                    onCheckedChange={() => toggle(i)}
                  />
                </TableCell>
                <TableCell className="font-medium">{item.description}</TableCell>
                <TableCell className="text-right">{item.quantity_text}</TableCell>
                <TableCell className="text-right">
                  {item.item_price_numeric
                    ? `$${item.item_price_numeric.toLocaleString()}`
                    : "-"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex justify-end">
        <Button
          onClick={() => onConfirm(Array.from(selected).sort((a, b) => a - b))}
          disabled={selected.size === 0}
          className="w-full bg-[#c00000] hover:bg-[#a00000] sm:w-auto"
        >
          Confirm Machines ({selected.size})
        </Button>
      </div>
    </div>
  );
}
