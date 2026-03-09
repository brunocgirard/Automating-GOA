import CorEditorPageClient from "@/components/pages/cor-editor-page-client";

export default async function CorEditorPage({
  params,
}: {
  params: Promise<{ corDocumentId: string }>;
}) {
  const { corDocumentId } = await params;
  return <CorEditorPageClient corDocumentId={corDocumentId} />;
}
