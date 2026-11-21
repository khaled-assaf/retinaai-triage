/**
 * Tiny fetch wrapper. All backend errors have body {"detail": "<message>"},
 * which we surface as ApiError so callers can toast `err.message`.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running on :8000?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body: unknown = await res.json();
      if (body && typeof body === "object" && "detail" in body) {
        detail = String((body as { detail: unknown }).detail);
      }
    } catch {
      // non-JSON error body, keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}
