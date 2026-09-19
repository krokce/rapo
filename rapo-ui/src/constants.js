// Control types (rapo_ref_types) with the Quasar color used for their chips, tabs and names.
export const CONTROL_TYPES = {
  ANL: { label: "Analysis", color: "pink-8" },
  REC: { label: "Reconciliation", color: "teal-8" },
  CMP: { label: "Comparison", color: "lime-8" },
  REP: { label: "Report", color: "indigo-6" },
};

export const CONTROL_TYPE_OPTIONS = Object.entries(CONTROL_TYPES).map(([value, type]) => ({ label: `${value} - ${type.label}`, value }));

export function controlTypeColor(type) {
  return CONTROL_TYPES[type] ? CONTROL_TYPES[type].color : "grey-6";
}

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
