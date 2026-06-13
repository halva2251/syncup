import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

interface GlossyButtonLinkProps
  extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "className" | "children"> {
  href: string;
  children: ReactNode;
  className?: string;
  loading?: boolean;
}

interface GlossyButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children"> {
  children: ReactNode;
  className?: string;
  loading?: boolean;
}

const shellClasses =
  "group relative inline-flex items-center justify-center overflow-hidden " +
  "rounded-lg bg-gradient-to-b from-[#60A5FA] to-[#1D4ED8] " +
  "px-5 py-2.5 text-sm font-semibold text-white shadow-md " +
  "transition-all duration-300 ease-out hover:shadow-lg active:scale-[0.98] " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] " +
  "disabled:cursor-not-allowed disabled:opacity-60";

const bezelStyle: React.CSSProperties = {
  border: "2px solid transparent",
  background:
    "linear-gradient(to bottom, rgba(0,0,0,0.18), rgba(255,255,255,0.22)) border-box, " +
    "linear-gradient(to bottom, rgba(0,0,0,0.08), rgba(255,255,255,0.1)) padding-box",
  WebkitMask: "linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0)",
  WebkitMaskComposite: "xor",
  maskComposite: "exclude",
};

function GlossyShell({
  children,
  loading,
}: {
  children: ReactNode;
  loading?: boolean;
}) {
  return (
    <>
      {/* Raised bezel / inner stroke */}
      <span
        className="pointer-events-none absolute inset-0 rounded-lg"
        style={bezelStyle}
      />
      {/* Gloss overlay — intensifies on hover so the lighter gradient stop appears even lighter */}
      <span className="pointer-events-none absolute inset-0 rounded-lg bg-gradient-to-b from-white/25 via-transparent to-transparent transition-all duration-300 ease-out group-hover:from-white/50" />
      {/* Content */}
      <span className="relative z-10 inline-flex items-center justify-center drop-shadow-md">
        <span className={loading ? "invisible" : undefined}>{children}</span>
        {loading && (
          <Loader2 className="absolute h-4 w-4 animate-spin" />
        )}
      </span>
    </>
  );
}

export function GlossyButtonLink({
  href,
  children,
  className,
  loading,
  ...props
}: GlossyButtonLinkProps) {
  return (
    <Link href={href} className={[shellClasses, className].filter(Boolean).join(" ")} {...props}>
      <GlossyShell loading={loading}>{children}</GlossyShell>
    </Link>
  );
}

export function GlossyButton({
  children,
  className,
  loading,
  type = "button",
  ...props
}: GlossyButtonProps) {
  return (
    <button
      type={type}
      className={[shellClasses, className].filter(Boolean).join(" ")}
      {...props}
    >
      <GlossyShell loading={loading}>{children}</GlossyShell>
    </button>
  );
}
