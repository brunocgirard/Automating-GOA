import QuoteClientInfoPageClient from "@/components/pages/quote-client-info-page-client";

export default async function QuoteClientInfoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <QuoteClientInfoPageClient key={id} id={id} />;
}
