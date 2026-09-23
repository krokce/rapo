// The email configuration of a control: rule_config.email (rapo/core/mailer.py). CMP keeps its rule_config as a list
// and has no email.

export const EMAIL_CONTROL_TYPES = ["ANL", "REP", "REC"];

export const SEND_WHEN_OPTIONS = [
  { label: "Done, with results", value: "done_with_results" },
  { label: "Done, always", value: "done" },
  { label: "Done or error", value: "done_or_error" },
];

// Result types a REC side can export: Loss and Discrepancy when its issues are saved, Match when its matches are.
export const REC_RESULT_TYPES = ["Loss", "Discrepancy", "Match"];

// The {variables} of the subject, the body and the sheet filters (mailer.build_variables). Dates carry a sample
// strftime format, since a bare datetime prints its time too.
export const EMAIL_VARIABLES = [
  { token: "{control_name}", label: "Control name" },
  { token: "{control_description}", label: "Control description" },
  { token: "{process_id}", label: "Process ID" },
  { token: "{control_date_from:%Y-%m-%d}", label: "Run from (date)" },
  { token: "{control_date_to:%Y-%m-%d}", label: "Run to (date)" },
  { token: "{control_date_from:%d.%m.%Y %H:%M:%S}", label: "Run from (date and time)" },
  { token: "{control_date_to:%d.%m.%Y %H:%M:%S}", label: "Run to (date and time)" },
  { token: "{status}", label: "Run status" },
  { token: "{start_date:%d.%m.%Y %H:%M:%S}", label: "Started" },
  { token: "{end_date:%d.%m.%Y %H:%M:%S}", label: "Ended" },
  { token: "{fetched_number}", label: "Fetched", single: true },
  { token: "{success_number}", label: "Success", single: true },
  { token: "{error_number}", label: "Errors", single: true },
  { token: "{fetched_number_a}", label: "Fetched A", rec: true },
  { token: "{fetched_number_b}", label: "Fetched B", rec: true },
  { token: "{success_number_a}", label: "Success A", rec: true },
  { token: "{success_number_b}", label: "Success B", rec: true },
  { token: "{error_number_a}", label: "Errors A", rec: true },
  { token: "{error_number_b}", label: "Errors B", rec: true },
  { token: "{attachment_rows}", label: "Attachment rows" },
];

// Metadata columns of the result tables (rapo/core/fields.py), offered while a result table does not exist yet.
export const RESULT_META_COLUMNS = {
  single: ["RAPO_RESULT_KEY", "RAPO_RESULT_VALUE", "RAPO_RESULT_TYPE", "RAPO_PROCESS_ID"],
  rec: ["RAPO_RESULT_TYPE", "RAPO_DISCREPANCY_ID", "RAPO_DISCREPANCY_DESCRIPTION", "RAPO_PROCESS_ID"],
};

const EMAIL_PATTERN = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/;

export function isEmailAddress(value) {
  return EMAIL_PATTERN.test(value);
}

// Characters Excel does not allow in a sheet name, which it also limits to 31 characters.
export const SHEET_NAME_INVALID = /[[\]:*?/\\]/;

// The sheet name used when none is set (mailer.build_sheets): the control name, or A / B for REC.
export function defaultSheetName(key, controlName) {
  return key === "main" ? (controlName || "").toUpperCase().slice(0, 31) : key.toUpperCase();
}

function defaultSheet(recSide) {
  const sheet = { name: null, filter: null, fields: [] };
  return recSide ? { enabled: true, result_types: [...REC_RESULT_TYPES], ...sheet } : sheet;
}

export function defaultEmailConfig(controlType) {
  return {
    enabled: false,
    send_when: "done_with_results",
    to: [],
    cc: [],
    bcc: [],
    subject: "{control_name} {control_date_from:%Y-%m-%d}",
    body: "",
    include_summary: true,
    attach: true,
    max_records: null,
    sheets: controlType === "REC" ? { a: defaultSheet(true), b: defaultSheet(true) } : { main: defaultSheet(false) },
  };
}

// Fill in what an older or hand-written configuration lacks, in place, so the editor can bind every field.
export function completeEmailConfig(email, controlType) {
  const defaults = defaultEmailConfig(controlType);
  for (const key of Object.keys(defaults)) {
    if (email[key] === undefined) {
      email[key] = defaults[key];
    }
  }
  for (const key of Object.keys(defaults.sheets)) {
    if (!email.sheets[key]) {
      email.sheets[key] = defaults.sheets[key];
    }
    for (const field of Object.keys(defaults.sheets[key])) {
      if (email.sheets[key][field] === undefined) {
        email.sheets[key][field] = defaults.sheets[key][field];
      }
    }
  }
  return email;
}

// Whether a catalogue row sends email, from its stored rule_config string.
export function sendsEmail(control) {
  if (!EMAIL_CONTROL_TYPES.includes(control.control_type) || !control.rule_config) {
    return false;
  }
  try {
    const ruleConfig = JSON.parse(control.rule_config);
    return Boolean(ruleConfig && ruleConfig.email && ruleConfig.email.enabled);
  } catch (error) {
    return false;
  }
}
