const API_BASE = "/api";

export function readCookie(name) {
  const prefix = `${name}=`;
  return document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length) ?? "";
}

export async function fetchJson(path, options = {}) {
  const method = options.method ?? "GET";
  const headers = new Headers(options.headers ?? {});
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;

  if (!isFormData && !headers.has("Content-Type") && method !== "GET" && method !== "HEAD") {
    headers.set("Content-Type", "application/json");
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = readCookie("oj_csrf");
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;

    try {
      const data = await response.json();

      if (Array.isArray(data.detail)) {
        detail = data.detail.map((e) => e.msg).join(", ");
      } else if (typeof data.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // Ignore non-JSON responses.
    }

    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}
