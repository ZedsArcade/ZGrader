"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useBranding } from "@/lib/branding-context";

export default function NavBar() {
  const { user, logout, loading } = useAuth();
  const { business_name } = useBranding();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link href="/" className="navbar-brand">
          {business_name}
        </Link>
        <div className="navbar-links">
          {loading ? null : user ? (
            <>
              {user.role === "operator" ? (
                <Link href="/admin">Admin</Link>
              ) : (
                <Link href="/dashboard">Dashboard</Link>
              )}
              <span className="muted" style={{ color: "#c3ccdf" }}>
                {user.email}
              </span>
              <button onClick={handleLogout} type="button" style={{ background: "none", border: "none", cursor: "pointer", font: "inherit" }}>
                Log out
              </button>
            </>
          ) : (
            <>
              <Link href="/login">Log in</Link>
              <Link href="/register">Register</Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
