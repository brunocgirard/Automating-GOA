"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getQuoteDetail,
  updateQuoteClientInfo,
  type QuoteDetail,
} from "@/lib/api";
import { QuoteClientInfo } from "@/components/quotes/quote-details";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Save, TableProperties } from "lucide-react";

interface QuoteClientInfoPageClientProps {
  id: string;
}

export default function QuoteClientInfoPageClient({ id }: QuoteClientInfoPageClientProps) {
  const [detail, setDetail] = useState<QuoteDetail | null>(null);
  const [clientInfo, setClientInfo] = useState<QuoteDetail["clientInfo"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void getQuoteDetail(id)
      .then((response) => {
        if (!active) return;
        setDetail(response);
        setClientInfo(response.clientInfo);
        setError(null);
        setStatusMessage(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load quote detail.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [id]);

  function handleClientChange(key: keyof QuoteDetail["clientInfo"], value: string) {
    setClientInfo((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function handleSave() {
    if (!detail || !clientInfo) return;

    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      await updateQuoteClientInfo(detail.quoteId, clientInfo);
      setStatusMessage("Changes saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save changes.");
    } finally {
      setSaving(false);
    }
  }

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

  if (!detail || !clientInfo) {
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
            <Link href={`/quotes/${id}`}>
              <TableProperties className="mr-1 size-4" />
              Line Items
            </Link>
          </Button>
          <Button onClick={handleSave} disabled={saving} className="w-full sm:w-auto">
            <Save className="mr-1 size-4" />
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Save failed: {error}
        </div>
      )}
      {statusMessage && (
        <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          {statusMessage}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Client Information</CardTitle>
        </CardHeader>
        <CardContent>
          <QuoteClientInfo clientInfo={clientInfo} onChange={handleClientChange} />
        </CardContent>
      </Card>
    </div>
  );
}
