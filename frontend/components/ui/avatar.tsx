import { UserRound } from "lucide-react";
import { cn } from "@/lib/utils/cn";

type AvatarSize = "sm" | "md" | "lg" | "xl";

interface AvatarProps {
  src?: string | null;
  alt: string;
  size?: AvatarSize;
  className?: string;
}

const sizeClasses: Record<AvatarSize, string> = {
  sm: "h-9 w-9",
  md: "h-12 w-12",
  lg: "h-16 w-16",
  xl: "h-24 w-24",
};

const iconSizes: Record<AvatarSize, string> = {
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-7 w-7",
  xl: "h-10 w-10",
};

/**
 * Circular avatar with a `UserRound` icon fallback when no `src` is provided.
 * Renders a plain `<img>` (no external domain config needed), matching the
 * existing profile-form avatar pattern.
 */
export function Avatar({ src, alt, size = "md", className }: AvatarProps) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-[var(--color-border)] bg-[var(--color-bg-page)]",
        sizeClasses[size],
        className,
      )}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={alt} className="h-full w-full object-cover" />
      ) : (
        <UserRound
          className={cn("text-[var(--color-text-tertiary)]", iconSizes[size])}
        />
      )}
    </div>
  );
}
