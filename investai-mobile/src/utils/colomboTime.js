// Sri Lanka time for greetings and "today", independent of the phone's clock
// zone. Asia/Colombo is a fixed UTC+05:30 with no daylight saving, so a plain
// offset is exact (Hermes' Intl time-zone support varies by build).
const OFFSET_MS = (5 * 60 + 30) * 60 * 1000;

// A Date whose UTC fields read as Colombo wall-clock time.
export const colomboNow = (now = new Date()) => new Date(now.getTime() + OFFSET_MS);

export function greetingKey(now = new Date()) {
  const h = colomboNow(now).getUTCHours();
  if (h >= 5 && h < 12) return 'home_greeting_morning';
  if (h >= 12 && h < 17) return 'home_greeting_afternoon';
  return 'home_greeting_evening';
}

export const colomboTodayLabel = (now = new Date()) =>
  colomboNow(now).toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC',
  });
