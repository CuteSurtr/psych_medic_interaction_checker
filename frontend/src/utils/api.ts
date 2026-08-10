export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_URL || "";
  if (path.startsWith("/")) return `${base}${path}`;
  return `${base}/${path}`;
}
