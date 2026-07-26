import ResetPasswordClient from "./reset-password-client";

// Next.js 16: dynamic route `params` is async and must be awaited in the
// server component before being handed to a client component.
export default async function ResetPasswordPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <ResetPasswordClient token={token} />;
}
