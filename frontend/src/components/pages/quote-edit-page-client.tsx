"use client";

import Link from "next/link";
import { getQuoteDetail, type QuoteDetail } from "@/lib/api";
import { useFetch } from "@/hooks/use-fetch";
import { ItemsTable } from "@/components/quotes/items-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, UserRound } from "lucide-react";

interface QuoteEditPageClientProps {
  id: string;
}

export default function QuoteEditPageClient({ id }: QuoteEditPageClientProps) {
  const { data: detail, loading, error } = useFetch<QuoteDetail>(
    async () => {
      try {
        return await getQuoteDetail(id);
      } catch (err) {
        throw err instanceof Error ? err : new Error("Failed to load quote detail.");
      }
    },
    [id]
  );

  if (loading) {
    return (
      <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
        Loading quote...
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Failed to load quote: {error}
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
        Quote not found.
      </div>
    );
  }

  const statusConfig = {
    draft: { label: "Draft", className: "bg-neutral-200 text-neutral-700" },
    processed: {
      label: "Processed",
      className: "bg-yellow-100 text-yellow-800",
    },
    ready: { label: "Ready", className: "bg-green-100 text-green-800" },
  } as const;
  const cfg = statusConfig[detail.status];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/">
              <ArrowLeft className="mr-1 size-4" />
              Back
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-2xl font-semibold tracking-tight">{detail.quoteRef}</h2>
              <Badge className={cfg.className} variant="secondary">
                {cfg.label}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">{detail.machineName}</p>
          </div>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <Button variant="outline" asChild className="w-full sm:w-auto">
            <Link href={`/client-info?quote=${id}`}>
              <UserRound className="mr-1 size-4" />
              Client Info
            </Link>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Line Items</CardTitle>
        </CardHeader>
        <CardContent>
          <ItemsTable items={detail.lineItems} />
        </CardContent>
      </Card>
    </div>
  );
}
