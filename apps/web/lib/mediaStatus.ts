export function mediaIsReady(status: string | undefined): boolean {
  return status === "ready";
}

export function mediaIsBusy(status: string | undefined): boolean {
  return status === "pending";
}

export function mediaIsFailed(status: string | undefined): boolean {
  return status === "error";
}

export function mediaStatusLabel(
  status: string | undefined,
  progress: string | undefined,
  pending: string,
  failed: string,
): string {
  const text = (progress || "").trim();
  if (mediaIsFailed(status)) return text || failed;
  if (mediaIsBusy(status)) return text || pending;
  return text;
}
