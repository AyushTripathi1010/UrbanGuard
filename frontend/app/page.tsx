"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const Heatmap = dynamic(() => import("@/components/HeatmapLayer"), { ssr: false });

type Alert = {
  alert_id: string;
  camera_id: string;
  zone_id: string;
  clip_label?: string;
  clip_score?: number;
  resnet_severity?: number;
  geo?: { lat: number; lon: number } | null;
  detected_at?: string;
};

const SEVERITY_FROM_SCORE = (s?: number) => {
  if (s === undefined) return "low";
  if (s >= 0.8) return "critical";
  if (s >= 0.55) return "high";
  return "low";
};

export default function Page() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    const src = new EventSource("/api/alerts/stream");
    src.addEventListener("alert", (e: MessageEvent) => {
      try {
        const alert = JSON.parse(e.data) as Alert;
        setAlerts(prev => [alert, ...prev].slice(0, 100));
      } catch {
        /* swallow malformed payloads */
      }
    });
    src.onerror = () => src.close();
    return () => src.close();
  }, []);

  return (
    <div className="layout">
      <div className="topbar">
        <span className="dot" />
        UrbanGuard live feed
        <span style={{ marginLeft: "auto", color: "#888" }}>{alerts.length} alerts</span>
      </div>
      <aside className="sidebar">
        <h2>Recent alerts</h2>
        {alerts.length === 0 ? (
          <div style={{ color: "#666" }}>
            Waiting for alerts. Start the ingest service and produce a clip.
          </div>
        ) : (
          alerts.map(a => {
            const sev = SEVERITY_FROM_SCORE(a.resnet_severity);
            return (
              <div key={a.alert_id} className={`alert-card ${sev}`}>
                <div className="meta">
                  <span>{a.camera_id} · {a.zone_id}</span>
                  <span>{(a.resnet_severity ?? 0).toFixed(2)}</span>
                </div>
                <div className="label">{a.clip_label ?? "incident"}</div>
              </div>
            );
          })
        )}
      </aside>
      <main className="map-pane">
        <Heatmap alerts={alerts} />
      </main>
    </div>
  );
}
