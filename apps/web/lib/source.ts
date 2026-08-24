export function isHttpUrl(value: string | null | undefined): value is string {
  return Boolean(value && (value.startsWith("http://") || value.startsWith("https://")));
}

export function displayUrl(value: string | null | undefined): string {
  if (!isHttpUrl(value)) {
    return "";
  }
  return value.replace(/^https?:\/\//, "").replace(/^www\./, "").split(/[?#]/)[0].replace(/\/$/, "");
}

export function faviconFromUrl(value: string | null | undefined): string {
  if (!isHttpUrl(value)) {
    return "";
  }
  const host = value.replace(/^https?:\/\//, "").split("/")[0];
  const scheme = value.startsWith("https://") ? "https" : "http";
  return `${scheme}://${host}/favicon.ico`;
}

export function sourceFavicon(origin: string | null | undefined, stored?: string | null): string {
  if (stored && !stored.startsWith("data:,") && stored !== "#") {
    return stored;
  }
  return faviconFromUrl(origin);
}
