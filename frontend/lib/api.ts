// Thin client helpers for the FastAPI gateway. Calls go through Next.js
// rewrites (next.config.mjs maps /api/* to http://localhost:8000/*).

export type Alert = {
  incident_id?: string;
  alert_id: string;
  camera_id: string;
  zone_id: string;
  clip_label?: string;
  clip_score?: number;
  resnet_severity?: number;
  geo?: { lat: number; lon: number } | null;
  created_at?: string;
};

export async function fetchRecentAlerts(limit = 50): Promise<Alert[]> {
  const r = await fetch(`/api/alerts?limit=${limit}`);
  if (!r.ok) return [];
  return r.json();
}

export async function fetchHeatmap(hours = 24) {
  const r = await fetch(`/api/heatmap?hours=${hours}`);
  if (!r.ok) return [];
  return r.json();
}
