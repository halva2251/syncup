import { useId } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export type SimpleIcon = {
  title: string;
  path: string;
};

export type AppIconGradient =
  | "blue"
  | "purple"
  | "green"
  | "orange"
  | "red"
  | "brand";

const gradients: Record<AppIconGradient, string> = {
  blue: "from-[var(--color-icon-gradient-blue-from)] to-[var(--color-icon-gradient-blue-to)]",
  purple: "from-[var(--color-icon-gradient-purple-from)] to-[var(--color-icon-gradient-purple-to)]",
  green: "from-[var(--color-icon-gradient-green-from)] to-[var(--color-icon-gradient-green-to)]",
  orange: "from-[var(--color-icon-gradient-orange-from)] to-[var(--color-icon-gradient-orange-to)]",
  red: "from-[var(--color-icon-gradient-red-from)] to-[var(--color-icon-gradient-red-to)]",
  brand: "from-[var(--color-icon-gradient-blue-from)] to-[var(--color-icon-gradient-blue-to)]",
};

const sizes = {
  xs: "w-8 h-8",
  sm: "w-10 h-10",
  md: "w-12 h-12",
  lg: "w-16 h-16",
  xl: "w-20 h-20",
  "2xl": "w-24 h-24",
  "3xl": "w-32 h-32",
  "4xl": "w-40 h-40",
};

const iconSizes = {
  xs: 20,
  sm: 24,
  md: 30,
  lg: 40,
  xl: 50,
  "2xl": 60,
  "3xl": 80,
  "4xl": 100,
};

const borderWidths: Record<keyof typeof sizes, number> = {
  xs: 1.5,
  sm: 2,
  md: 2.5,
  lg: 3,
  xl: 4,
  "2xl": 5,
  "3xl": 5,
  "4xl": 6,
};

type AppIconProps =
  | {
      icon: LucideIcon;
      brand?: never;
      size?: keyof typeof sizes;
      gradient?: AppIconGradient;
      brandColor?: string;
      /** Override the glyph size while keeping the selected container size. */
      iconSize?: number;
      glossy?: boolean;
      className?: string;
    }
  | {
      icon?: never;
      brand: SimpleIcon;
      size?: keyof typeof sizes;
      gradient?: AppIconGradient;
      brandColor?: string;
      /** Override the glyph size while keeping the selected container size. */
      iconSize?: number;
      glossy?: boolean;
      className?: string;
    };

export function AppIcon({
  icon,
  brand,
  size = "md",
  gradient = "blue",
  brandColor,
  iconSize,
  glossy = true,
  className,
}: AppIconProps) {
  const id = useId().replace(/:/g, "");
  const IconComponent = icon;
  const gradientUrl = `url(#${id}-iconGradient)`;
  const renderedIconSize = iconSize ?? iconSizes[size];

  return (
    <span
      className={cn(
        "relative inline-flex items-center justify-center shrink-0 overflow-hidden",
        "rounded-[22%] shadow-md",
        sizes[size],
        !brandColor && "bg-gradient-to-b",
        !brandColor && gradients[gradient],
        className,
      )}
      style={brandColor ? { backgroundColor: brandColor } : undefined}
    >
      {/* Raised bezel / inner border */}
      <span
        className="pointer-events-none absolute inset-0 rounded-[22%]"
        style={{
          border: `${borderWidths[size]}px solid transparent`,
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0.18), rgba(255,255,255,0.22)) border-box, linear-gradient(to bottom, rgba(0,0,0,0.08), rgba(255,255,255,0.1)) padding-box",
          WebkitMask: "linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0)",
          WebkitMaskComposite: "xor",
          maskComposite: "exclude",
        }}
      />

      {/* Gloss overlay */}
      {glossy && (
        <span className="pointer-events-none absolute inset-0 rounded-[22%] bg-gradient-to-b from-white/25 via-transparent to-transparent" />
      )}

      {/* Gradient definition for the icon */}
      <svg width="0" height="0" className="absolute">
        <defs>
          <linearGradient
            id={`${id}-iconGradient`}
            x1="0"
            y1="0"
            x2="0"
            y2="24"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor="rgba(255, 255, 255, 1)" />
            <stop offset="55%" stopColor="rgba(255, 255, 255, 0.65)" />
            <stop offset="100%" stopColor="rgba(255, 255, 255, 0.25)" />
          </linearGradient>
        </defs>
      </svg>

      {/* Icon */}
      {IconComponent ? (
        <IconComponent
          size={renderedIconSize}
          className="relative z-10 drop-shadow-2xl"
          strokeWidth={2}
          style={{ stroke: gradientUrl }}
        />
      ) : brand ? (
        <svg
          viewBox="0 0 24 24"
          width={renderedIconSize}
          height={renderedIconSize}
          className="relative z-10 drop-shadow-2xl"
          aria-label={brand.title}
          role="img"
          style={{ fill: gradientUrl }}
        >
          <path d={brand.path} />
        </svg>
      ) : null}
    </span>
  );
}
