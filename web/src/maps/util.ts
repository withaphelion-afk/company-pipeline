import { J } from "../api";

export const STATUSES = ["new", "contacted", "replied", "quoted", "won", "lost"];

/** wa.me link with the message pre-filled; 10-digit numbers are assumed to be Indian (+91). */
export function whatsapp(phone: string, text: string): string | null {
  let d = (phone || "").replace(/\D/g, "");
  if (d.startsWith("0")) d = d.slice(1);
  if (d.length === 10) d = "91" + d;
  return d.length >= 11 ? `https://wa.me/${d}?text=${encodeURIComponent(text)}` : null;
}

export function pitchFor(template: string, l: J): string {
  const area = (l.address || "").split(",")[0];
  return template.replaceAll("{name}", l.name).replaceAll("{category}", (l.category || "business").toLowerCase()).replaceAll("{area}", area);
}
