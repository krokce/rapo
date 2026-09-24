// code-compare exists only in Font Awesome 6; the app loads the v5 font, so it is imported as an SVG icon.
import { fasCodeCompare } from "@quasar/extras/fontawesome-v6";

// Control types (rapo_ref_types) with the icon and Quasar color used for their chips, tabs and names.
export const CONTROL_TYPES = {
  ANL: { label: "Analysis", icon: "fas fa-microscope", color: "pink-8" },
  REC: { label: "Reconciliation", icon: fasCodeCompare, color: "teal-8" },
  CMP: { label: "Comparison", icon: "fas fa-not-equal", color: "lime-8" },
  REP: { label: "Report", icon: "fas fa-file-alt", color: "indigo-6" },
};

export const CONTROL_TYPE_OPTIONS = Object.entries(CONTROL_TYPES).map(([value, type]) => ({ label: `${value} - ${type.label}`, value }));

export function controlTypeColor(type) {
  return CONTROL_TYPES[type] ? CONTROL_TYPES[type].color : "grey-6";
}

export function controlType(type) {
  return CONTROL_TYPES[type] || { label: type || "Unknown", icon: "fas fa-question-circle", color: "grey-6" };
}

// KPI type chips: one icon for all, the avatar colored by the unit (racs_kpi_type.kpi_value_unit, free text).
// The common units are pinned; any other unit is hashed into a palette without their colors, so it never looks
// like one of them.
export const KPI_ICON = "fas fa-calculator";

const KPI_UNIT_COLORS = { rec: "blue-8", "%": "orange-8", "€": "green-8", pts: "purple-7", mb: "cyan-8" };

const KPI_UNIT_PALETTE = [
  "red-7",
  "brown-6",
  "deep-purple-6",
  "light-green-8",
  "amber-9",
  "blue-grey-7",
  "pink-6",
];

export function kpiUnitColor(unit) {
  const key = (unit || "").trim().toLowerCase();
  if (!key) return "blue-grey-4";
  if (KPI_UNIT_COLORS[key]) return KPI_UNIT_COLORS[key];
  let hash = 0;
  for (const char of key) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  return KPI_UNIT_PALETTE[hash % KPI_UNIT_PALETTE.length];
}

// Control engines (rapo_ref_engines). DB runs the SQL pipeline from Python, PL
// runs it inside Oracle through RAPO_USAGE_RULE, PY is referenced but not built.
export const CONTROL_ENGINES = {
  DB: { label: "Database SQL" },
  PY: { label: "Python" },
  PL: { label: "PL-SQL procedure" },
};

export const CONTROL_ENGINE_OPTIONS = Object.entries(CONTROL_ENGINES).map(([value, engine]) => ({ label: `${value} - ${engine.label}`, value }));

// Run statuses (rapo_log.status), in lifecycle order.
export const RUN_STATUSES = {
  I: { label: "Initiated", icon: "fas fa-plus-circle", color: "indigo" },
  W: { label: "Waiting", icon: "fas fa-pause-circle", color: "amber-7" },
  S: { label: "Started", icon: "fas fa-play-circle", color: "blue" },
  P: { label: "Running", icon: "fas fa-sync fa-spin", color: "blue" },
  F: { label: "Finishing", icon: "fas fa-circle-notch fa-spin", color: "blue" },
  D: { label: "Done", icon: "fas fa-check-circle", color: "green" },
  E: { label: "Error", icon: "fas fa-exclamation-circle", color: "deep-orange" },
  C: { label: "Canceled", icon: "fas fa-times-circle", color: "purple-3" },
  X: { label: "Revoked", icon: "fas fa-times-circle", color: "grey" },
};

export const RUN_STATUS_OPTIONS = Object.entries(RUN_STATUSES).map(([value, status]) => ({ label: status.label, value }));

// Runs in these statuses can still be canceled.
export const ACTIVE_RUN_STATUSES = ["I", "W", "S", "P", "F"];

export function runStatus(status) {
  if (!status) {
    return { label: "Void", icon: "fas fa-times-circle", color: "deep-purple-3" };
  }
  return RUN_STATUSES[status] || { label: "Unknown", icon: "fas fa-question-circle", color: "grey" };
}

export const YES_NO_OPTIONS = [
  { label: "Yes", value: "Y" },
  { label: "No", value: "N" },
];

export const PERIOD_TYPE_OPTIONS = [
  { label: "Day", value: "D" },
  { label: "Week", value: "W" },
  { label: "Month", value: "M" },
];

// Scheduler event types (rapo_scheduler_event.event_type): what happened to one run request.
export const SCHEDULER_EVENT_TYPES = {
  FIRED: { label: "Queued", icon: "fas fa-hourglass-half", color: "indigo" },
  STARTED: { label: "Started", icon: "fas fa-play-circle", color: "blue" },
  MISSED: { label: "Missed", icon: "fas fa-exclamation-triangle", color: "amber-8" },
  FAILED: { label: "Failed", icon: "fas fa-exclamation-circle", color: "deep-orange" },
  CANCELED: { label: "Canceled", icon: "fas fa-times-circle", color: "purple-3" },
};

export const SCHEDULER_EVENT_TYPE_OPTIONS = Object.entries(SCHEDULER_EVENT_TYPES).map(([value, type]) => ({ label: type.label, value }));

export function schedulerEventType(type) {
  return SCHEDULER_EVENT_TYPES[type] || { label: type || "Unknown", icon: "fas fa-question-circle", color: "grey" };
}

// What requested a run (rapo_scheduler_event.trigger_type).
export const TRIGGER_TYPES = {
  SCHEDULE: { label: "Schedule", icon: "fas fa-clock" },
  MANUAL: { label: "Manual", icon: "fas fa-user" },
  CATCHUP: { label: "Catch-up", icon: "fas fa-history" },
  ITERATION: { label: "Iteration", icon: "fas fa-redo" },
  CASCADE: { label: "Cascade", icon: "fas fa-sitemap" },
};

export const TRIGGER_TYPE_OPTIONS = Object.entries(TRIGGER_TYPES).map(([value, type]) => ({ label: type.label, value }));

// Scheduler states reported by /scheduler-status for this server.
export const SCHEDULER_STATES = {
  running: { label: "Running", color: "teal", description: "This server runs the scheduler." },
  standby: { label: "Standby", color: "blue-grey", description: "Another server runs the scheduler, this one takes over if it stops." },
  starting: { label: "Starting", color: "amber-8", description: "The scheduler is acquiring its lease." },
  stopped: { label: "Stopped", color: "deep-orange", description: "The scheduler was stopped from the UI on all servers." },
  off: { label: "Off", color: "grey", description: "The scheduler is disabled for this server (rapo.ini or development mode)." },
};

export function schedulerState(state) {
  return SCHEDULER_STATES[state] || { label: state || "Unknown", color: "grey", description: "" };
}
