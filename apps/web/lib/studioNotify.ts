export const STUDIO_NOTIFY_PREF_KEY = "studio-notify";

export type StudioNotifyPref = "on" | "off";
export type NotifyPermission = "granted" | "denied" | "default" | "unsupported";

export type StudioStatusItem = {
  id: string;
  title: string;
  payload?: { status?: string; progress?: string };
};

export function notificationSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

export function notificationPermission(): NotifyPermission {
  if (!notificationSupported()) return "unsupported";
  return Notification.permission;
}

export function loadStudioNotifyPref(): StudioNotifyPref | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STUDIO_NOTIFY_PREF_KEY);
  if (raw === "on" || raw === "off") return raw;
  return null;
}

export function saveStudioNotifyPref(pref: StudioNotifyPref): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STUDIO_NOTIFY_PREF_KEY, pref);
}

export function studioNotifyWanted(): boolean {
  return loadStudioNotifyPref() !== "off";
}

export function studioNotifyEnabled(): boolean {
  return notificationPermission() === "granted" && studioNotifyWanted();
}

export function artifactStatusMap(artifacts: StudioStatusItem[]): Record<string, string> {
  return Object.fromEntries(artifacts.map((item) => [item.id, item.payload?.status || "ready"]));
}

export function finishedStudioArtifacts(
  prevStatus: Record<string, string>,
  artifacts: StudioStatusItem[],
): StudioStatusItem[] {
  return artifacts.filter((item) => {
    const before = prevStatus[item.id];
    const status = item.payload?.status || "ready";
    return before === "pending" && status !== "pending";
  });
}

export async function requestStudioNotifyPermission(): Promise<NotifyPermission> {
  if (!notificationSupported()) return "unsupported";
  const current = Notification.permission;
  if (current !== "default") {
    if (current === "granted") saveStudioNotifyPref("on");
    return current;
  }
  const next = await Notification.requestPermission();
  if (next === "granted") saveStudioNotifyPref("on");
  if (next === "denied") saveStudioNotifyPref("off");
  return next;
}

export function notifyStudioJob(input: { title: string; body: string; tag?: string }): void {
  if (!studioNotifyEnabled()) return;
  const notification = new Notification(input.title, {
    body: input.body,
    tag: input.tag || "studio-job",
  });
  notification.onclick = () => {
    window.focus();
    notification.close();
  };
}
