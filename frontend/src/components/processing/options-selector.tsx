"use client";

import { useState } from "react";
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
import type { LineItem } from "@/lib/types";

interface OptionItem {
  index: number;
  item: LineItem;
}

interface OptionsSelectorProps {
  items: OptionItem[];
  onConfirm: (selectedIndices: number[]) => void;
}

export function OptionsSelector({ items, onConfirm }: OptionsSelectorProps) {
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const toggle = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(items.map((entry) => entry.index)));
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-lg font-semibold">Select Common Options</h3>
        <Button variant="outline" onClick={selectAll} className="w-full sm:w-auto">
          Select All Common
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
            {items.map((entry) => (
              <TableRow key={entry.index}>
                <TableCell>
                  <Checkbox
                    checked={selected.has(entry.index)}
                    onCheckedChange={() => toggle(entry.index)}
                  />
                </TableCell>
                <TableCell className="font-medium">{entry.item.description}</TableCell>
                <TableCell className="text-right">{entry.item.quantity_text}</TableCell>
                <TableCell className="text-right">
                  {entry.item.item_price_numeric
                    ? `$${entry.item.item_price_numeric.toLocaleString()}`
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
          Confirm Options ({selected.size})
        </Button>
      </div>
    </div>
  );
}
