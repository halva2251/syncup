import type { ReactNode } from "react";
import Link from "next/link";
import { AppIcon } from "@/components/ui/app-icon";
import { Sparkles } from "lucide-react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--color-bg-page)] p-4">
      <div className="w-full max-w-[420px]">
        <Link
          href="/"
          className="mb-10 flex items-center justify-center gap-3 text-[var(--color-text-primary)]"
        >
          <AppIcon icon={Sparkles} size="md" gradient="brand" />
          <span className="text-2xl font-bold tracking-tight">SyncUp</span>
        </Link>
        {children}
      </div>
    </div>
  );
}
