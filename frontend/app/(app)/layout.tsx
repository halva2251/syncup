import { ToastProvider } from "@/components/ui/toast-provider";
import { redirect } from "next/navigation";
import { AppFooter } from "@/components/navigation/app-footer";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";

export default async function Layout({ children }: { children: React.ReactNode }) {
  let user;
  try {
    ({ user } = await getCurrentUser());
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  return (
    <>
      <main className="min-h-screen pb-[calc(6rem+env(safe-area-inset-bottom))] sm:pb-[calc(7rem+env(safe-area-inset-bottom))]">
        {children}
      </main>
      <AppFooter avatarUrl={user.avatar_url} displayName={user.display_name} />
      <ToastProvider />
    </>
  );
}
