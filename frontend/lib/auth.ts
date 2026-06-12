"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:3000";

interface AuthResponse {
  user: {
    id: string;
    email: string;
    display_name: string;
  };
}

interface BackendError {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

function parseSetCookieHeader(header: string) {
  const [nameValue, ...attrs] = header.split(";").map((part) => part.trim());
  const [name, value] = nameValue.split("=");
  const options: Record<string, unknown> = {};

  for (const attr of attrs) {
    const [key, rawValue] = attr.split("=");
    const lowerKey = key.toLowerCase();
    if (lowerKey === "expires") {
      options.expires = new Date(rawValue);
    } else if (lowerKey === "max-age") {
      options.maxAge = Number.parseInt(rawValue, 10);
    } else if (lowerKey === "path") {
      options.path = rawValue;
    } else if (lowerKey === "domain") {
      options.domain = rawValue;
    } else if (lowerKey === "secure") {
      options.secure = true;
    } else if (lowerKey === "httponly") {
      options.httpOnly = true;
    } else if (lowerKey === "samesite") {
      options.sameSite = rawValue.toLowerCase() as "strict" | "lax" | "none";
    }
  }

  return { name, value, options };
}

async function forwardCookies(response: Response) {
  const setCookieHeader = response.headers.getSetCookie?.() ?? response.headers.get("set-cookie")?.split(", ") ?? [];
  const cookieStore = await cookies();

  for (const header of setCookieHeader) {
    if (!header) continue;
    const { name, value, options } = parseSetCookieHeader(header);
    cookieStore.set(name, decodeURIComponent(value), {
      path: "/",
      ...options,
    });
  }
}

async function postAuth(path: string, body: object) {
  const cookieStore = await cookies();

  const response = await fetch(`${BACKEND_URL}/api${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Cookie: cookieStore.toString(),
    },
    body: JSON.stringify(body),
  });

  const data = (await response.json()) as AuthResponse | BackendError;

  if (!response.ok) {
    const error = (data as BackendError).error;
    return {
      error: error?.message ?? "Something went wrong. Please try again.",
    };
  }

  forwardCookies(response);
  return { user: (data as AuthResponse).user };
}

export async function login(formData: FormData) {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;

  if (!email || !password) {
    return { error: "Email and password are required." };
  }

  const result = await postAuth("/auth/login", { email, password });

  if ("error" in result) {
    return result;
  }

  redirect("/home");
}

export async function signup(formData: FormData) {
  const email = formData.get("email") as string;
  const displayName = formData.get("display_name") as string;
  const password = formData.get("password") as string;

  if (!email || !displayName?.trim() || !password) {
    return { error: "Email, display name, and password are required." };
  }

  const result = await postAuth("/auth/signup", {
    email,
    display_name: displayName.trim(),
    password,
  });

  if ("error" in result) {
    return result;
  }

  redirect("/onboarding");
}
