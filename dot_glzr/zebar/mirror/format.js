export const escape = value => String(value ?? "").replace(/[&<>"']/g,
  char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
export const gib = bytes => (bytes / 1024 ** 3).toFixed(1);
// Keep binary units for disk tooltips.
export function diskSize(bytes) {
  let unit = 0;
  while (bytes >= 1024 && unit < 5) { bytes /= 1024; unit++; }
  return `${bytes.toFixed(1)}${["B", "kiB", "MiB", "GiB", "TiB", "PiB"][unit]}`;
}
export const freeGigabytes = bytes => `${Math.round(bytes / 1000 ** 3).toString().padStart(4)}G`;
export const clamp = value => Math.max(0, Math.min(100, value));
// Zebar's Windows provider returns locale tags (sometimes with a trailing NUL),
// not the human-readable layout names supplied by Hyprland.
const cleanLayout = layout => String(layout ?? "").replace(/\0/g, "").trim();
export function language(layout) {
  const name = cleanLayout(layout);
  return /^(en|eng)(?:[-_]|$)|english/i.test(name) ? "eng"
    : /^(ar|ara)(?:[-_]|$)|arabic/i.test(name) ? "ara" : "---";
}
export function keyboardName(layout) {
  const name = cleanLayout(layout);
  if (!name) return "Keyboard unavailable";
  if (!/^[a-z]{2,3}(?:[-_][a-z0-9]{2,8})*$/i.test(name)) return name;
  try {
    const locale = new Intl.Locale(name.replace(/_/g, "-"));
    const languageName = new Intl.DisplayNames(["en"], { type: "language" }).of(locale.language);
    const region = locale.region && new Intl.DisplayNames(["en"], { type: "region" }).of(locale.region);
    return region ? `${languageName} (${region})` : languageName;
  } catch { return name; }
}
export function speed(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  let unit = 0;
  bytes = Math.floor(bytes);
  // numfmt rounds away from zero, promoting a rounded 1000 to the next unit.
  while (Math.ceil(bytes) >= 1000 && unit < 5) { bytes /= 1000; unit++; }
  return `${Math.ceil(bytes)}${[" ", "k", "M", "G", "T", "P"][unit]}`.padStart(4);
}
export function networkSample(previous, current) {
  if (!current || !Number.isFinite(current.receivedBytes) || !Number.isFinite(current.timestamp)) return null;
  const elapsed = previous && (current.timestamp - previous.timestamp) / 1000;
  const bytes = previous && current.interfaceId === previous.interfaceId && elapsed > 0
    && current.receivedBytes >= previous.receivedBytes
    ? (current.receivedBytes - previous.receivedBytes) / elapsed : 0;
  return { ...current, bytesPerSecond: bytes };
}
export function weatherData(json) {
  const current = json?.current_condition?.[0];
  const area = json?.nearest_area?.[0];
  if (!current || !Number.isFinite(Number(current.temp_F))) return null;
  const code = String(current.weatherCode);
  const snow = "179 182 185 227 230 320 323 326 329 332 335 338 368 371 374 377".split(" ");
  const rain = "176 263 266 281 284 293 296 299 302 305 308 311 314 317 350 353 356 359 362 365".split(" ");
  const icon = code === "113" ? "󰖙" : ["143", "248", "260"].includes(code) ? "󰖑"
    : snow.includes(code) ? "󰖘" : ["200", "386", "389"].includes(code) ? "󰖓"
    : rain.includes(code) ? "󰖗" : "󰖐";
  return {
    text: `${icon} ${String(current.temp_F).padStart(3)}°F`,
    tooltip: `${area?.areaName?.[0]?.value ?? "Unknown location"}, ${area?.country?.[0]?.value ?? ""}\n`
      + `${current.weatherDesc?.[0]?.value ?? ""}\nFeels like ${current.FeelsLikeF}°F · Humidity ${current.humidity}% · Wind ${current.windspeedKmph} km/h`,
  };
}
export function clockText(now, locale) {
  const pad = n => String(n).padStart(2, "0");
  return `${pad(now.getHours())}:${pad(now.getMinutes())} | ${now.toLocaleDateString(locale, { weekday: "short" })} `
    + `${pad(now.getDate())} ${now.toLocaleDateString(locale, { month: "short" }).slice(0, 3)}`;
}
export function calendar(now, locale) {
  const year = now.getFullYear(), month = now.getMonth();
  const first = (new Date(year, month, 1).getDay() + 6) % 7;
  const days = new Date(year, month + 1, 0).getDate();
  const cells = Array.from({ length: first }, () => "    ");
  for (let day = 1; day <= days; day++) {
    cells.push(day === now.getDate() ? `[${String(day).padStart(2)}]` : ` ${String(day).padStart(2)} `);
  }
  const rows = [];
  for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7).join(" "));
  return `${year} ${now.toLocaleDateString(locale, { month: "long" })}\n Mon  Tue  Wed  Thu  Fri  Sat  Sun\n${rows.join("\n")}`;
}
