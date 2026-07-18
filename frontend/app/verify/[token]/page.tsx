import VerifyClient from "./verify-client";

// Next.js 16: dynamic route `params` is async and must be awaited in the
// server component before being handed to a client component.
export default async function VerifyPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <VerifyClient token={token} />;
}
