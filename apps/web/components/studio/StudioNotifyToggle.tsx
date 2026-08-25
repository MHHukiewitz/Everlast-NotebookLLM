"use client";

import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import {
  loadStudioNotifyPref,
  notificationPermission,
  requestStudioNotifyPermission,
  saveStudioNotifyPref,
  type NotifyPermission,
} from "@/lib/studioNotify";

export function StudioNotifyToggle({ hint }: { hint?: string }) {
  const [perm, setPerm] = useState<NotifyPermission>("unsupported");
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const next = notificationPermission();
    setPerm(next);
    setChecked(next !== "denied" && loadStudioNotifyPref() !== "off");
  }, []);

  if (perm === "unsupported") return null;

  return (
    <div className="space-y-1">
      {hint ? <p className="text-xs text-neutral-500">{hint}</p> : null}
      {perm === "denied" ? (
        <p className="text-xs text-neutral-500">{t.notifyStudioDenied}</p>
      ) : (
        <label className="flex items-start gap-2 text-xs">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={checked}
            onChange={(event) => {
              const want = event.target.checked;
              setChecked(want);
              if (!want) {
                saveStudioNotifyPref("off");
                return;
              }
              void requestStudioNotifyPermission().then((next) => {
                setPerm(next);
                setChecked(next !== "denied" && loadStudioNotifyPref() !== "off");
              });
            }}
          />
          <span>{t.notifyStudioAsk}</span>
        </label>
      )}
    </div>
  );
}
