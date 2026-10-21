// Access of the signed-in token (whoami): the master token may do everything, a user token what its scopes {area: level}
// allow. Levels include the ones below them; rapo/web/api/scopes.py is the rule the server enforces.
export const LEVELS = ["none", "view", "operate", "edit"];

export const LEVEL_LABELS = { none: "None", view: "View", operate: "Operate", edit: "Edit" };

// The lifetimes a token is created or extended with (rapo/web/api/tokens.py DURATIONS).
export const TOKEN_DURATIONS = [
  { value: "1m", label: "1 month" },
  { value: "6m", label: "6 months" },
  { value: "1y", label: "1 year" },
  { value: "unlimited", label: "Unlimited" },
];

// Days before the expiry a user token warns about it.
export const EXPIRY_WARNING_DAYS = 14;

export function allows(whoami, area, level = "view") {
  if (!whoami) {
    return false;
  }
  if (whoami.master) {
    return true;
  }
  const held = (whoami.scopes || {})[area] || "none";
  return LEVELS.indexOf(held) >= LEVELS.indexOf(level);
}

export function hasFreeSql(whoami) {
  return Boolean(whoami && (whoami.master || whoami.free_sql));
}

// Whether a route's page is open to the token: route meta.scope = [area, level], meta.master for the master token only.
export function routeAllowed(whoami, route) {
  const meta = (route && route.meta) || {};
  if (meta.master) {
    return Boolean(whoami && whoami.master);
  }
  return !meta.scope || allows(whoami, ...meta.scope);
}

// Whole days until a date (naive ISO, the server's clock), negative once past; null without a date.
export function daysUntil(date) {
  if (!date) {
    return null;
  }
  return Math.floor((new Date(date).getTime() - Date.now()) / 86400000);
}

// "Runs: Operate · Data: View ..." for the areas a token reaches, in the order of areas.
export function scopeSummary(scopes, areas) {
  return (areas || [])
    .filter((item) => scopes && scopes[item.area] && scopes[item.area] !== "none")
    .map((item) => `${item.title}: ${LEVEL_LABELS[scopes[item.area]]}`);
}
