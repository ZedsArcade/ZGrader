import SubmissionDetailClient from "./detail-client";

// Next.js 16: dynamic route `params` is async and must be awaited in the
// server component before being handed to a client component.
export default async function SubmissionDetailPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  return <SubmissionDetailClient code={code} />;
}
