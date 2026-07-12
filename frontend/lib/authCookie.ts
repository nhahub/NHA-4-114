/**
 * lib/authCookie.ts
 * Sets/clears the `svs_auth` session cookie that middleware.ts reads.
 * This is a non-httpOnly, session-scoped cookie — it contains NO sensitive data.
 * The actual JWT lives only in memory (lib/auth.ts).
 *
 * Call setAuthCookie() right after a successful login.
 * Call clearAuthCookie() on logout.
 */

export function setAuthCookie(): void {
  if (typeof document === "undefined") return;
  // Session cookie — expires when browser closes
  document.cookie = "svs_auth=1; path=/; SameSite=Lax";
}

export function clearAuthCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = "svs_auth=; path=/; max-age=0; SameSite=Lax";
}
