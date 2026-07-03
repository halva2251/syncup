/**
 * Join class names, filtering out falsy values.
 *
 * NOTE: This is intentionally a simple joiner, not a tailwind-merge replacement.
 * When class conflicts become common, replace with clsx + tailwind-merge.
 */
export function cn(...inputs: (string | undefined | null | false)[]): string {
  return inputs.filter(Boolean).join(" ");
}
