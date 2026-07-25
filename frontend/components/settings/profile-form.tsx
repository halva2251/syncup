"use client";

import { useActionState, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2, UserRound } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ErrorMessage } from "@/components/ui/error-message";
import { LanguageSelect } from "@/components/ui/language-select";
import { toast } from "@/components/ui/toast";
import {
  updateProfileAction,
  uploadAvatarAction,
} from "@/lib/actions/settings-actions";

const AVATAR_ACCEPT = "image/png,image/jpeg,image/webp,image/gif";
const AVATAR_MAX_BYTES = 5 * 1024 * 1024;

interface ProfileFormProps {
  initialDisplayName: string;
  initialBio: string | null;
  initialDiscordHandle: string | null;
  initialAvatarUrl: string | null;
  initialLanguages: string[] | null;
}

function AvatarUpload({ initialAvatarUrl }: { initialAvatarUrl: string | null }) {
  const router = useRouter();
  const [avatarUrl, setAvatarUrl] = useState<string | null>(initialAvatarUrl);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (!AVATAR_ACCEPT.split(",").includes(file.type)) {
      toast.error("Choose a PNG, JPEG, WebP, or GIF image.");
      return;
    }
    if (file.size > AVATAR_MAX_BYTES) {
      toast.error("Image must be 5 MB or smaller.");
      return;
    }

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file));

    const formData = new FormData();
    formData.append("file", file);
    startTransition(async () => {
      try {
        const result = await uploadAvatarAction(formData);
        if ("error" in result && result.error) {
          toast.error(result.error);
          setPreviewUrl(null);
        } else {
          setAvatarUrl(result.avatar_url ?? null);
          toast.success("Photo updated");
          router.refresh();
        }
      } catch {
        // The action can throw (e.g. payload exceeds the framework body limit)
        // before our error handling runs — surface it as a toast instead of
        // letting it crash the page.
        toast.error("That image is too large to upload. Try one under 5 MB.");
        setPreviewUrl(null);
      }
    });
  }

  const shown = previewUrl ?? avatarUrl;

  return (
    <div>
      <span className="mb-2 block text-[15px] font-medium text-[var(--color-text-primary)]">
        Profile photo
      </span>
      <div className="flex flex-col items-start gap-3 min-[400px]:flex-row min-[400px]:items-center min-[400px]:gap-4">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[var(--color-border)] bg-[var(--color-bg-page)]">
          {shown ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={shown} alt="Profile photo" className="h-full w-full object-cover" />
          ) : (
            <UserRound className="h-7 w-7 text-[var(--color-text-tertiary)]" />
          )}
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-accent-light)] px-3 py-2 text-sm text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-accent-soft)]">
          {isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Uploading…
            </>
          ) : (
            "Change photo"
          )}
          <input
            type="file"
            name="file"
            accept={AVATAR_ACCEPT}
            onChange={handleChange}
            disabled={isPending}
            className="sr-only"
          />
        </label>
      </div>
      <p className="mt-1.5 text-xs text-[var(--color-text-tertiary)]">
        PNG, JPEG, WebP, or GIF — up to 5 MB.
      </p>
    </div>
  );
}

export function ProfileForm({
  initialDisplayName,
  initialBio,
  initialDiscordHandle,
  initialAvatarUrl,
  initialLanguages,
}: ProfileFormProps) {
  const router = useRouter();
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>(
    initialLanguages ?? [],
  );

  const [state, formAction, pending] = useActionState(
    async (_prevState: { error?: string; success?: boolean } | null, formData: FormData) => {
      // Inject the current language selection into the form payload.
      formData.set("languages", JSON.stringify(selectedLanguages));
      const result = await updateProfileAction(formData);
      if ("error" in result && result.error) {
        toast.error(result.error);
        return { error: result.error };
      }
      toast.success("Profile saved");
      router.refresh();
      return { success: true };
    },
    null,
  );

  return (
    <form action={formAction} className="space-y-4 sm:space-y-5">
      {state?.error && <ErrorMessage>{state.error}</ErrorMessage>}

      <Input
        name="display_name"
        label="Display name"
        defaultValue={initialDisplayName}
        placeholder="Your name"
        required
        maxLength={200}
      />

      <div>
        <label
          htmlFor="bio"
          className="mb-2 block text-[15px] font-medium text-[var(--color-text-primary)]"
        >
          Bio
        </label>
        <textarea
          id="bio"
          name="bio"
          rows={4}
          defaultValue={initialBio ?? ""}
          placeholder="A short intro — what are you into?"
          maxLength={500}
          className="w-full resize-y rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3.5 py-2 text-[15px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-bg-page)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-[3px] focus:ring-[var(--color-accent-soft)]"
        />
        <p className="mt-1.5 text-xs text-[var(--color-text-tertiary)]">
          Shown on your public taste card and match profile.
        </p>
      </div>

      <Input
        name="discord_handle"
        label="Discord handle"
        defaultValue={initialDiscordHandle ?? ""}
        placeholder="username or username#1234"
      />

      <AvatarUpload initialAvatarUrl={initialAvatarUrl} />

      <LanguageSelect
        name="languages"
        label="Languages you speak"
        selected={selectedLanguages}
        onChange={setSelectedLanguages}
        placeholder="Add languages..."
      />

      <div className="flex items-center justify-stretch gap-2 border-t border-[var(--color-border-subtle)] pt-4 sm:justify-end sm:pt-5">
        <Button type="submit" disabled={pending} className="relative w-full sm:w-auto">
          <span className={pending ? "invisible" : undefined}>Save changes</span>
          {pending && <Loader2 className="absolute h-4 w-4 animate-spin" />}
        </Button>
      </div>
    </form>
  );
}
