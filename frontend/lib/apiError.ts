import axios from "axios";

/**
 * Normalize FastAPI / axios errors into a single user-facing string.
 */
export function parseApiError(err: unknown): string {
  if (!axios.isAxiosError(err)) {
    return err instanceof Error ? err.message : "Something went wrong. Please try again.";
  }

  const detail = err.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = Array.isArray(d.loc) ? d.loc.slice(1).join(".") : "field";
        return `${field}: ${d.msg ?? "invalid"}`;
      })
      .join("; ");
  }

  if (err.response?.status === 401) {
    return "Incorrect username or password";
  }

  return err.message || "Request failed. Please try again.";
}
