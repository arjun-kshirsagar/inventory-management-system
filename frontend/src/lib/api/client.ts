import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

let accessToken: string | null = null;
let refreshing: Promise<string | null> | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

/** Exchange the httpOnly refresh cookie for a new access token (deduplicated). */
export function refreshAccessToken(): Promise<string | null> {
  refreshing ??= fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin" })
    .then(async (res) => (res.ok ? ((await res.json()) as { access_token: string }).access_token : null))
    .catch(() => null)
    .then((token) => {
      accessToken = token;
      refreshing = null;
      return token;
    });
  return refreshing;
}

const authMiddleware: Middleware = {
  onRequest({ request }) {
    if (accessToken) request.headers.set("Authorization", `Bearer ${accessToken}`);
    return request;
  },
};

/** Fetch that retries once with a refreshed token on 401. */
async function authFetch(input: Request): Promise<Response> {
  const retry = input.clone();
  const res = await fetch(input);
  if (res.status !== 401 || input.url.includes("/auth/")) return res;
  const token = await refreshAccessToken();
  if (!token) {
    onUnauthorized?.();
    return res;
  }
  retry.headers.set("Authorization", `Bearer ${token}`);
  return fetch(retry);
}

export const api = createClient<paths>({ baseUrl: "", fetch: authFetch });
api.use(authMiddleware);

export class ApiError extends Error {}

/** Pull a readable message out of a FastAPI error body. */
export function errorMessage(error: unknown): string {
  if (!error) return "Something went wrong";
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  const detail = (error as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: (string | number)[]; msg?: string }) =>
        [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": "),
      )
      .join("; ");
  }
  return "Something went wrong";
}

/** Unwrap an openapi-fetch result, throwing a readable error. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    if (result.response.ok && result.data === undefined) return undefined as T;
    throw new ApiError(errorMessage(result.error));
  }
  return result.data;
}

/** Authenticated GET for binary/CSV endpoints. */
export async function fetchFile(path: string): Promise<Blob> {
  const res = await authFetch(
    new Request(path, { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} }),
  );
  if (!res.ok) throw new ApiError(errorMessage(await res.json().catch(() => null)));
  return res.blob();
}

export async function postFile(path: string, body: unknown): Promise<Blob> {
  const res = await authFetch(
    new Request(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify(body),
    }),
  );
  if (!res.ok) throw new ApiError(errorMessage(await res.json().catch(() => null)));
  return res.blob();
}

export function openBlob(blob: Blob) {
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
