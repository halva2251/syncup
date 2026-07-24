"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { BACKEND_URL } from "@/lib/constants/backend-url";

export async function logoutAction() {
  const cookieStore = await cookies();

  const response = await fetch(`${BACKEND_URL}/api/auth/logout`, {
    method: "POST",
    headers: { Cookie: cookieStore.toString() },
  });

  if (!response.ok) {
    throw new Error("Could not log out. Please try again.");
  }

  // The backend clears its cookie response, but Server Actions must also
  // remove the cookie stored by Next for the browser-facing origin.
  cookieStore.delete("syncup_session");
  redirect("/login");
}
