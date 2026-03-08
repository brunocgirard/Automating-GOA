import QuotePreviewPageClient from "@/components/pages/quote-preview-page-client";

export default async function QuotePreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <QuotePreviewPageClient id={id} />;
}
