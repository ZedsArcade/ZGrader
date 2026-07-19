"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Spinner } from "@heroui/react";
import { useAuth } from "@/lib/auth-context";
import type { UserRole } from "@/lib/api";

export default function RequireAuth({ children, role }: { children: ReactNode; role?: UserRole }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (role && user.role !== role) {
      router.replace("/dashboard");
    }
  }, [loading, user, role, router]);

  if (loading || !user || (role && user.role !== role)) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  return <>{children}</>;
}
