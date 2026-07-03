import { cookies } from "next/headers";
import { BACKEND_URL } from "@/lib/constants/backend-url";
import type { ApiErrorBody } from "@/types/api";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const cookieStore = await cookies();
  const url = `${BACKEND_URL}/api${path}`;
  const body = options.body;
  const shouldSetJsonContentType =
    body !== undefined &&
    !(body instanceof FormData) &&
    !new Headers(options.headers).has("Content-Type");

  const response = await fetch(url, {
    ...options,
    headers: {
      ...(shouldSetJsonContentType ? { "Content-Type": "application/json" } : {}),
      Cookie: cookieStore.toString(),
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody | Record<string, never>;
    const error = "error" in body ? body.error : null;
    throw new ApiError(
      error?.code ?? "UNKNOWN_ERROR",
      error?.message ?? `Request failed with status ${response.status}`,
      response.status
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
