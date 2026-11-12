// Formatting helpers shared by the pages (units follow the desktop app: m/km, km/h, degrees).
export const dist = m => (m === null || m === undefined ? '–' : m < 1000 ? `${m.toFixed(0)} m` : `${(m / 1000).toFixed(2)} km`);
export const kmh = ms => (ms === null || ms === undefined ? '–' : `${(ms * 3.6).toFixed(1)} km/h`);
export const deg = d => (d === null || d === undefined ? '–' : `${d.toFixed(1)}°`);
export const num = (v, d = 1, u = '') => (v === null || v === undefined ? '–' : `${Number(v).toFixed(d)}${u}`);
export function dur(s) {
  if (s === null || s === undefined || !Number.isFinite(s)) return '–';
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return h ? `${h} h ${String(m).padStart(2, '0')} min` : m ? `${m} min ${String(x).padStart(2, '0')} s` : `${x} s`;
}
export function clock(t, basis) {
  if (t === null || t === undefined) return '–';
  if (basis === 'time of day') { const s = ((t % 86400) + 86400) % 86400; return new Date(s * 1000).toISOString().slice(11, 19) + ' UTC'; }
  return new Date(t * 1000).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
}
export const accuracy = a => (a === null || a === undefined ? '–' : a >= 999 ? 'no fix' : a < 1000 ? `${a.toFixed(1)} m` : `${(a / 1000).toFixed(1)} km`);
