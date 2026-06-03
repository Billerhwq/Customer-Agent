import type { LeadFields } from "./api";

const FLAGS: Record<string, string> = {
  germany: "🇩🇪", mexico: "🇲🇽", "united states": "🇺🇸", usa: "🇺🇸", us: "🇺🇸",
  canada: "🇨🇦", france: "🇫🇷", italy: "🇮🇹", spain: "🇪🇸", netherlands: "🇳🇱",
  uk: "🇬🇧", "united kingdom": "🇬🇧", japan: "🇯🇵", korea: "🇰🇷",
  australia: "🇦🇺", brazil: "🇧🇷", india: "🇮🇳", china: "🇨🇳",
};

export function flagOf(country?: string | null): string {
  if (!country) return "🌐";
  return FLAGS[country.trim().toLowerCase()] ?? "🌐";
}

export function timeHM(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function relativeDay(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const days = Math.floor((+now - +d) / 86400000);
  if (days <= 0) return timeHM(iso);
  if (days === 1) return "昨天";
  return `${days}天前`;
}

export const LEAD_LABELS: { key: keyof LeadFields; label: string }[] = [
  { key: "product", label: "产品 Product" },
  { key: "quantity", label: "数量 Quantity" },
  { key: "country", label: "国家 Country" },
  { key: "material", label: "材料 Material" },
  { key: "email", label: "邮箱 Email" },
  { key: "drawing_available", label: "图纸 Drawing" },
];

export function leadFilledCount(lead: LeadFields): number {
  return LEAD_LABELS.filter(({ key }) => {
    const v = lead[key];
    return v !== null && v !== undefined && v !== "";
  }).length;
}

export function confidenceTier(v: number): { label: string; cls: string } {
  if (v >= 0.7) return { label: "高", cls: "tier-high" };
  if (v >= 0.4) return { label: "中", cls: "tier-mid" };
  return { label: "低", cls: "tier-low" };
}

export function copyText(t: string) {
  if (navigator.clipboard) navigator.clipboard.writeText(t).catch(() => {});
}

export function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}
