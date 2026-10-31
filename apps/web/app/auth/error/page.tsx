/**
 * Minimal sign-in failure page.  Lands here when /auth/callback can't
 * exchange the OAuth code for a session (expired code, missing env,
 * Supabase outage, …).
 */
import Link from "next/link";

export default async function AuthErrorPage({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string }>;
}) {
  const { reason = "unknown" } = await searchParams;
  return (
    <main className="min-h-screen bg-bg text-fg flex items-center justify-center px-6">
      <div className="max-w-md w-full text-center space-y-3">
        <h1 className="text-[18px] font-semibold">Sign-in failed</h1>
        <p className="text-[13px] text-muted leading-snug">
          Supabase couldn&apos;t complete the OAuth round-trip. This usually
          resolves by trying again; if it persists, the cause shows up
          below.
        </p>
        <pre className="text-[11px] font-mono text-subtle bg-fg/[0.03] border border-line rounded px-3 py-2 text-left overflow-x-auto">
          reason: {reason}
        </pre>
        <Link
          href="/"
          className="inline-block text-[13px] px-4 py-2 rounded-md bg-warn/15 text-warn border border-warn/30 hover:bg-warn/25 font-medium"
        >
          Back to home
        </Link>
      </div>
    </main>
  );
}
