import GoaFormPageClient from "@/components/pages/goa-form-page-client";

export default async function GoaFormPage({
  params,
}: {
  params: Promise<{ machineTemplateId: string }>;
}) {
  const { machineTemplateId } = await params;
  return <GoaFormPageClient machineTemplateId={machineTemplateId} />;
}
