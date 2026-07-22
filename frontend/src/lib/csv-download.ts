import { apiClient } from "../api/client";

/**
 * Fetch a CSV endpoint with the current auth token and trigger a browser
 * download. We can't just `<a href>` a CSV endpoint because the auth
 * interceptor injects the Bearer token from the Zustand store — a plain
 * link would send an unauthenticated request and 401.
 */
export async function downloadCsv(path: string, fallbackFilename: string): Promise<void> {
  const response = await apiClient.get<Blob>(path, { responseType: "blob" });

  // Extract filename from Content-Disposition if present; fall back to
  // the caller-provided default. Server currently always sends one, but
  // the fallback keeps the download working if a proxy strips headers.
  const cd = String(response.headers["content-disposition"] ?? "");
  const match = cd.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] ?? fallbackFilename;

  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
