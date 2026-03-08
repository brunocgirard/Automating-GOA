import GoaDocumentBuilderPageClient from "@/components/pages/goa-document-builder-page-client";

export default async function GoaDocumentBuilderPage({
  params,
}: {
  params: Promise<{ machineTemplateId: string }>;
}) {
  const { machineTemplateId } = await params;
  return <GoaDocumentBuilderPageClient machineTemplateId={machineTemplateId} />;
}
