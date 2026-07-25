"use client";

import { useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Check, Loader2, Pencil, UserRound, X } from "lucide-react";
import { LanguageSelect } from "@/components/ui/language-select";
import { toast } from "@/components/ui/toast";
import {
  updateProfileDetailsAction,
  uploadAvatarAction,
} from "@/lib/actions/settings-actions";
import { getLanguageFlag, getLanguageName } from "@/lib/constants/languages";

const AVATAR_ACCEPT = "image/png,image/jpeg,image/webp,image/gif";
const AVATAR_MAX_BYTES = 5 * 1024 * 1024;

interface EditableProfileDetailsProps {
  initialDisplayName: string;
  initialBio: string | null;
  initialAvatarUrl: string | null;
  initialLanguages: string[] | null;
}

export function EditableProfileDetails({
  initialDisplayName,
  initialBio,
  initialAvatarUrl,
  initialLanguages,
}: EditableProfileDetailsProps) {
  const router = useRouter();
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const [savedDisplayName, setSavedDisplayName] = useState(initialDisplayName);
  const [displayName, setDisplayName] = useState(initialDisplayName);
  const [savedBio, setSavedBio] = useState(initialBio ?? "");
  const [bio, setBio] = useState(initialBio ?? "");
  const [avatarUrl, setAvatarUrl] = useState(initialAvatarUrl);
  const [savedLanguages, setSavedLanguages] = useState(initialLanguages ?? []);
  const [languages, setLanguages] = useState(initialLanguages ?? []);
  const [editing, setEditing] = useState<"name" | "bio" | "languages" | null>(null);
  const [isPending, startTransition] = useTransition();

  function save(updates: { display_name?: string; bio?: string; languages?: string[] }, done: () => void) {
    startTransition(async () => {
      const result = await updateProfileDetailsAction(updates);
      if ("error" in result && result.error) {
        toast.error(result.error);
        return;
      }
      done();
      router.refresh();
    });
  }

  function saveName() {
    const nextName = displayName.trim();
    if (nextName === savedDisplayName) {
      setEditing(null);
      return;
    }
    save({ display_name: nextName }, () => {
      setSavedDisplayName(nextName);
      setDisplayName(nextName);
      setEditing(null);
    });
  }

  function saveBio() {
    const nextBio = bio.trim();
    if (nextBio === savedBio) {
      setEditing(null);
      return;
    }
    save({ bio: nextBio }, () => {
      setSavedBio(nextBio);
      setBio(nextBio);
      setEditing(null);
    });
  }

  function uploadAvatar(file: File) {
    if (!AVATAR_ACCEPT.split(",").includes(file.type)) {
      toast.error("Choose a PNG, JPEG, WebP, or GIF image.");
      return;
    }
    if (file.size > AVATAR_MAX_BYTES) {
      toast.error("Image must be 5 MB or smaller.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    startTransition(async () => {
      const result = await uploadAvatarAction(formData);
      if ("error" in result && result.error) {
        toast.error(result.error);
        return;
      }
      setAvatarUrl(result.avatar_url ?? null);
      toast.success("Photo updated");
      router.refresh();
    });
  }

  return (
    <section className="flex items-start gap-4">
      <div className="group relative shrink-0">
        <button
          type="button"
          onClick={() => avatarInputRef.current?.click()}
          disabled={isPending}
          className="relative flex h-20 w-20 items-center justify-center overflow-hidden rounded-full border border-[var(--color-border)] bg-[var(--color-bg-page)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] disabled:cursor-wait"
          aria-label="Change profile photo"
        >
          {avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={avatarUrl} alt="Profile photo" className="h-full w-full object-cover" />
          ) : (
            <UserRound className="h-8 w-8 text-[var(--color-text-tertiary)]" />
          )}
          <span className="absolute inset-0 flex items-center justify-center bg-black/55 text-center text-xs font-medium text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Edit photo"}
          </span>
        </button>
        <input
          ref={avatarInputRef}
          type="file"
          accept={AVATAR_ACCEPT}
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) uploadAvatar(file);
          }}
        />
      </div>

      <div className="min-w-0 flex-1 space-y-1 pt-1">
        {editing === "name" ? (
          <input
            autoFocus
            value={displayName}
            maxLength={200}
            disabled={isPending}
            onChange={(event) => setDisplayName(event.target.value)}
            onBlur={saveName}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
              if (event.key === "Escape") {
                setDisplayName(savedDisplayName);
                setEditing(null);
              }
            }}
            className="w-full rounded-md border border-[var(--color-accent)] bg-[var(--color-bg-card)] px-1.5 py-0.5 text-xl font-semibold text-[var(--color-text-primary)] outline-none ring-[3px] ring-[var(--color-accent-soft)]"
            aria-label="Display name"
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditing("name")}
            className="group flex max-w-full items-center gap-2 rounded-md px-1.5 py-0.5 -ml-1.5 text-left transition-colors hover:bg-[var(--color-bg-page)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
            aria-label="Edit display name"
          >
            <span className="truncate text-xl font-semibold text-[var(--color-text-primary)]">{displayName}</span>
            <Pencil className="h-4 w-4 shrink-0 text-[var(--color-text-tertiary)] opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
          </button>
        )}

        {editing === "bio" ? (
          <textarea
            autoFocus
            value={bio}
            rows={3}
            maxLength={500}
            disabled={isPending}
            onChange={(event) => setBio(event.target.value)}
            onBlur={saveBio}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setBio(savedBio);
                setEditing(null);
              }
            }}
            placeholder="Add a short introduction"
            className="mt-1 w-full resize-none rounded-md border border-[var(--color-accent)] bg-[var(--color-bg-card)] px-1.5 py-1 text-sm leading-relaxed text-[var(--color-text-secondary)] outline-none ring-[3px] ring-[var(--color-accent-soft)]"
            aria-label="Bio"
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditing("bio")}
            className="group mt-1 flex w-full items-start gap-2 rounded-md px-1.5 py-1 -ml-1.5 text-left transition-colors hover:bg-[var(--color-bg-page)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
            aria-label="Edit bio"
          >
            <span className="flex-1 text-sm leading-relaxed text-[var(--color-text-secondary)]">
              {bio || "Add a short introduction"}
            </span>
            <Pencil className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-text-tertiary)] opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
          </button>
        )}

        {editing === "languages" ? (
          <div className="mt-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] p-3">
            <LanguageSelect
              name="languages"
              selected={languages}
              onChange={setLanguages}
              placeholder="Add languages..."
            />
            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setLanguages(savedLanguages);
                  setEditing(null);
                }}
                className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-page)]"
              >
                <X className="h-3.5 w-3.5" /> Cancel
              </button>
              <button
                type="button"
                disabled={isPending}
                onClick={() => save({ languages }, () => {
                  setSavedLanguages(languages);
                  setEditing(null);
                })}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-accent)] px-2.5 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
              >
                {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                Save
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setEditing("languages")}
            className="group mt-2 flex flex-wrap items-center gap-1.5 rounded-md p-1 -ml-1 transition-colors hover:bg-[var(--color-bg-page)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
            aria-label="Edit languages"
          >
            {languages.length > 0 ? languages.map((code) => {
              const flag = getLanguageFlag(code);
              return <span key={code} className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-accent-soft)] px-2 py-0.5 text-xs font-medium text-[var(--color-accent)]">
                {flag ? <span className={`fi fi-${flag} h-3 w-4 rounded-sm`} /> : null}
                {getLanguageName(code) ?? code}
              </span>;
            }) : <span className="text-sm text-[var(--color-text-tertiary)]">Add languages</span>}
            <Pencil className="h-3.5 w-3.5 text-[var(--color-text-tertiary)] opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
          </button>
        )}
      </div>
    </section>
  );
}
