import {
  Music,
  Gamepad2,
  Film,
  BookOpen,
  Tv,
  Sparkles,
  BookOpenText,
  Users,
  HelpCircle,
  type LucideIcon,
} from "lucide-react";

export const CATEGORY_ICONS: Record<string, LucideIcon> = {
  game: Gamepad2,
  music: Music,
  film: Film,
  book: BookOpen,
  show: Tv,
  anime: Sparkles,
  manga: BookOpenText,
  community: Users,
  other: HelpCircle,
};
