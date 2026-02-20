"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchQuoteWorkflowStatus,
  getQuoteDetail,
  updateQuoteClientInfo,
  type QuoteDetail,
  type QuoteWorkflowStatus,
} from "@/lib/api";
import { QuoteClientInfo } from "@/components/quotes/quote-details";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Save, TableProperties } from "lucide-react";

interface QuoteClientInfoPageClientProps {
  id: string;
}

function formatStatusTimestamp(value: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function workflowQuoteBadgeConfig(
  status: QuoteWorkflowStatus["quoteStatus"] | null | undefined
): { label: string; className: string } {
  if (status === "ready") {
    return { label: "Ready", className: "bg-green-100 text-green-800" };
  }
  if (status === "processed") {
    return { label: "Processed", className: "bg-yellow-100 text-yellow-800" };
  }
  return { label: "Draft", className: "bg-neutral-200 text-neutral-700" };
}

export default function QuoteClientInfoPageClient({ id }: QuoteClientInfoPageClientProps) {
  const [detail, setDetail] = useState<QuoteDetail | null>(null);
  const [clientInfo, setClientInfo] = useState<QuoteDetail["clientInfo"] | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<QuoteWorkflowStatus | null>(null);
  const [workflowLoading, setWorkflowLoading] = useState(true);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
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

  useEffect(() => {
    const quoteId = Number(id);
    if (!Number.isFinite(quoteId)) {
      setWorkflowStatus(null);
      setWorkflowError("Invalid quote id.");
      setWorkflowLoading(false);
      return;
    }

    let active = true;
    setWorkflowLoading(true);
    setWorkflowError(null);

    void fetchQuoteWorkflowStatus(quoteId)
      .then((response) => {
        if (!active) return;
        setWorkflowStatus(response);
      })
      .catch((err) => {
        if (!active) return;
        setWorkflowStatus(null);
        setWorkflowError(err instanceof Error ? err.message : "Failed to load workflow status.");
      })
      .finally(() => {
        if (active) setWorkflowLoading(false);
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
  const quoteWorkflowBadge = workflowQuoteBadgeConfig(workflowStatus?.quoteStatus);

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
          <CardTitle>Workflow Status</CardTitle>
        </CardHeader>
        <CardContent>
          {workflowLoading ? (
            <div className="rounded-md border bg-white p-4 text-sm text-muted-foreground">
              Loading workflow status...
            </div>
          ) : workflowError ? (
            <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              Failed to load workflow status: {workflowError}
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-md border bg-white p-4">
                <p className="text-xs font-medium text-muted-foreground">Quote Processing</p>
                <div className="mt-2">
                  <Badge
                    className={quoteWorkflowBadge.className}
                    variant="secondary"
                  >
                    {quoteWorkflowBadge.label}
                  </Badge>
                </div>
              </div>

              <div className="rounded-md border bg-white p-4">
                <p className="text-xs font-medium text-muted-foreground">Shipping Documents</p>
                <div className="mt-2">
                  <Badge
                    className={
                      workflowStatus?.shippingSaved
                        ? "bg-green-100 text-green-800"
                        : "bg-neutral-200 text-neutral-700"
                    }
                    variant="secondary"
                  >
                    {workflowStatus?.shippingSaved ? "Saved" : "Not started"}
                  </Badge>
                </div>
                {workflowStatus?.shippingSaved && workflowStatus.shippingModifiedDate ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Last update: {formatStatusTimestamp(workflowStatus.shippingModifiedDate)}
                  </p>
                ) : null}
              </div>

              <div className="rounded-md border bg-white p-4">
                <p className="text-xs font-medium text-muted-foreground">COR</p>
                <div className="mt-2">
                  <Badge
                    className={
                      workflowStatus?.corSaved
                        ? "bg-green-100 text-green-800"
                        : "bg-neutral-200 text-neutral-700"
                    }
                    variant="secondary"
                  >
                    {workflowStatus?.corSaved ? "Saved" : "Not started"}
                  </Badge>
                </div>
                {workflowStatus?.corSaved && workflowStatus.corModifiedDate ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Last update: {formatStatusTimestamp(workflowStatus.corModifiedDate)}
                  </p>
                ) : null}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

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
