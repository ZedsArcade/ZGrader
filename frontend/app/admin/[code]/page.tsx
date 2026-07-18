import AdminDetailClient from "./admin-detail-client";

// Next.js 16: dynamic route `params` is async and must be awaited in the
// server component before being handed to a client component.
export default async function AdminSubmissionPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  return <AdminDetailClient code={code} />;
}
