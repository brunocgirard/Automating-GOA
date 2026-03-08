import QuoteEditPageClient from "@/components/pages/quote-edit-page-client";

export default async function QuoteEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <QuoteEditPageClient key={id} id={id} />;
}
