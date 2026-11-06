// Frontend configuration. API base URL is configurable via VITE_API_BASE_URL.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
