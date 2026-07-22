"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Compass,
  Home,
  Settings,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { cn } from "@/lib/utils/cn";

interface AppFooterProps {
  userId: string;
  avatarUrl: string | null;
  displayName: string;
}

interface FooterLink {
  href: string;
  label: string;
  icon: LucideIcon;
  matches: (pathname: string) => boolean;
}

function FooterTooltip({ children }: { children: React.ReactNode }) {
  return (
    <span className="pointer-events-none absolute bottom-[calc(100%+0.75rem)] left-1/2 -translate-x-1/2 translate-y-1 whitespace-nowrap rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-2.5 py-1 text-xs font-medium text-[var(--color-text-primary)] opacity-0 shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-[opacity,transform] group-hover:translate-y-0 group-hover:opacity-100 group-focus-visible:translate-y-0 group-focus-visible:opacity-100">
      {children}
    </span>
  );
}

const FOOTER_LINKS: FooterLink[] = [
  {
    href: "/home",
    label: "Home",
    icon: Home,
    matches: (pathname) => pathname === "/home",
  },
  {
    href: "/feed",
    label: "Feed",
    icon: Sparkles,
    matches: (pathname) => pathname === "/feed" || pathname.startsWith("/feed/"),
  },
  {
    href: "/recommendations",
    label: "Recommendations",
    icon: Compass,
    matches: (pathname) => pathname === "/recommendations",
  },
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
    matches: (pathname) => pathname === "/settings" || pathname.startsWith("/settings/"),
  },
];

/**
 * The signed-in app's fixed, icon-only navigation dock.
 *
 * Onboarding has its own stepper, so the dock stays out of that focused flow.
 */
export function AppFooter({ userId, avatarUrl, displayName }: AppFooterProps) {
  const pathname = usePathname();

  if (pathname.startsWith("/onboarding")) {
    return null;
  }

  const profileHref = `/feed/${userId}`;
  const profileIsActive = pathname === profileHref;

  return (
    <footer
      aria-label="Primary navigation"
      className="pointer-events-none fixed inset-x-0 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-40 flex justify-center px-4 sm:bottom-[calc(1.5rem+env(safe-area-inset-bottom))]"
    >
      <nav className="pointer-events-auto flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-card)] p-1.5 shadow-[0_1px_2px_rgba(0,0,0,0.08)]">
        {FOOTER_LINKS.map((link) => {
          const Icon = link.icon;
          const isActive = link.matches(pathname);

          return (
            <Link
              key={link.href}
              href={link.href}
              aria-label={link.label}
              title={link.label}
              className={cn(
                "group relative inline-flex h-10 w-10 items-center justify-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] sm:h-11 sm:w-11",
                isActive
                  ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-page)] hover:text-[var(--color-text-primary)]",
              )}
            >
              <Icon className="h-5 w-5" strokeWidth={isActive ? 2 : 1.75} />
              <span className="sr-only">{link.label}</span>
              <FooterTooltip>{link.label}</FooterTooltip>
            </Link>
          );
        })}

        <span className="mx-0.5 h-7 w-px bg-[var(--color-border)]" aria-hidden="true" />

        <Link
          href={profileHref}
          aria-label="Your profile"
          title="Your profile"
          className={cn(
            "group relative inline-flex h-10 w-10 items-center justify-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] sm:h-11 sm:w-11",
            profileIsActive
              ? "bg-[var(--color-accent-soft)]"
              : "hover:bg-[var(--color-bg-page)]",
          )}
        >
          <Avatar
            src={avatarUrl}
            alt={`${displayName}'s profile`}
            size="sm"
            className={cn(
              "h-8 w-8 transition-transform sm:h-9 sm:w-9",
              profileIsActive && "border-[var(--color-accent)]",
            )}
          />
          <span className="sr-only">Your profile</span>
          <FooterTooltip>Profile</FooterTooltip>
        </Link>
      </nav>
    </footer>
  );
}
