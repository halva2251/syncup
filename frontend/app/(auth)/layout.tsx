import type { ReactNode } from "react";
import Link from "next/link";
import { Heart } from "lucide-react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--color-bg-page)] p-4">
      <div className="w-full max-w-[400px]">
        <Link
          href="/"
          className="mb-8 flex items-center justify-center gap-2 text-[var(--color-text-primary)]"
        >
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-accent)] text-white">
            <Heart className="h-4 w-4 fill-current" />
          </span>
          <span className="text-xl font-bold tracking-tight">SyncUp</span>
        </Link>
        {children}
      </div>
    </div>
  );
}
