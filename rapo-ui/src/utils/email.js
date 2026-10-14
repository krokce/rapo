// The email configuration of a control: rule_config.email (rapo/core/mailer.py). CMP keeps its rule_config as a list
// and has no email. Its attachments are `files`, each an Excel file of `sheets` (result or Free SQL sheets).

export const EMAIL_CONTROL_TYPES = ["ANL", "REP", "REC"];

export const SEND_WHEN_OPTIONS = [
  { label: "Done, with results", value: "done_with_results" },
  { label: "Done, always", value: "done" },
  { label: "Done or error", value: "done_or_error" },
  { label: "Evaluate SQL", value: "evaluate_sql" },
];

// Result types a REC side can export: Loss and Discrepancy when its issues are saved, Match when its matches are.
export const REC_RESULT_TYPES = ["Loss", "Discrepancy", "Match"];

// The {variables} of the subject, the body, the attachment name and the sheet queries (mailer.build_variables).
// Dates carry a sample strftime format, since a bare datetime prints its time too. `sheets: false` marks the ones
// that are empty while the sheets are built, so the filter and Free SQL boxes do not offer them.
export const EMAIL_VARIABLES = [
  { token: "{control_name}", label: "Control name" },
  { token: "{control_description}", label: "Control description" },
  { token: "{process_id}", label: "Process ID" },
  { token: "{control_date:%Y-%m-%d}", label: "Run date" },
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
  { token: "{attachment_rows}", label: "Attachment rows", sheets: false },
  { token: "{evaluate_value}", label: "Evaluate SQL value", evaluate: true },
];

// The variables of a control type's subject, body and attachment name; {evaluate_value} only with send_when
// 'evaluate_sql'.
export function emailVariables(controlType, sendWhen) {
  const rec = controlType === "REC";
  return EMAIL_VARIABLES.filter((variable) => (rec ? !variable.single : !variable.rec) && (!variable.evaluate || sendWhen === "evaluate_sql"));
}

// The variables of the sheet filters and the Free SQL, as CodeBox `templateVars`: one entry per variable, dates with
// their first sample format.
export function sheetVariables(controlType) {
  const seen = new Set();
  return emailVariables(controlType)
    .filter((variable) => variable.sheets !== false)
    .map((variable) => {
      const [name, format] = variable.token.slice(1, -1).split(/:(.*)/);
      return { name, format: format || null, label: variable.label.replace(/ \(date( and time)?\)$/, "") };
    })
    .filter((variable) => !seen.has(variable.name) && seen.add(variable.name));
}

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

// The result types a REC side saves (mailer.available_result_types): Loss and Discrepancy with its issues, Match with
// its matches.
export function availableResultTypes(ruleConfig, side) {
  const rule = ruleConfig || {};
  return [...(rule["need_issues_" + side] ? ["Loss", "Discrepancy"] : []), ...(rule["need_recons_" + side] ? ["Match"] : [])];
}

// The result types a REC sheet exports (mailer.chosen_result_types), in their fixed order.
export function chosenResultTypes(sheet, ruleConfig) {
  const available = availableResultTypes(ruleConfig, sheet.side);
  const chosen = sheet.result_types && sheet.result_types.length ? sheet.result_types : available;
  return REC_RESULT_TYPES.filter((type) => chosen.includes(type) && available.includes(type));
}

// A result sheet of the control's result table (side "main") or of a REC side, with every type the side saves.
export function defaultResultSheet(side, ruleConfig) {
  const sheet = { kind: "result", side, name: null, filter: null, fields: [] };
  if (side === "main") return sheet;
  const available = ruleConfig ? availableResultTypes(ruleConfig, side) : [];
  return { ...sheet, result_types: available.length ? available : [...REC_RESULT_TYPES] };
}

// A Free SQL sheet (mailer.SqlSheet): a query of the user's own.
export function defaultSqlSheet() {
  return { kind: "sql", name: null, query: null };
}

// One attached file with the default sheets: the result table, or both REC sides.
export function defaultFile(controlType, ruleConfig) {
  const sides = controlType === "REC" ? ["a", "b"] : ["main"];
  return { name: null, attach: true, sheets: sides.map((side) => defaultResultSheet(side, ruleConfig)) };
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
    max_records: null,
    files: [defaultFile(controlType)],
  };
}

// An older configuration (one attachment_name, attach and a fixed `sheets` object) as `files`, in place, as
// mailer.read_files reads it: its enabled sheets main (or A, B) then the Free SQL; a REC sheet without a name keeps
// its old default A / B.
function convertLegacyEmail(email, controlType) {
  if (Array.isArray(email.files)) return;
  const legacy = email.sheets || {};
  const sheets = [];
  const sides = controlType === "REC" ? ["a", "b"] : ["main"];
  sides.forEach((side) => {
    const config = legacy[side] || {};
    if (!(config.enabled === undefined ? side === "main" : config.enabled)) return;
    const sheet = { kind: "result", side, name: config.name || null, filter: config.filter || null, fields: config.fields || [] };
    if (side !== "main") {
      sheet.name = sheet.name || side.toUpperCase();
      sheet.result_types = config.result_types && config.result_types.length ? [...config.result_types] : [...REC_RESULT_TYPES];
    }
    sheets.push(sheet);
  });
  const sql = legacy.sql || {};
  if (sql.enabled) {
    sheets.push({ kind: "sql", name: sql.name || null, query: sql.query || null });
  }
  email.files = [{ name: email.attachment_name || null, attach: email.attach !== false, sheets }];
  delete email.attachment_name;
  delete email.attach;
  delete email.sheets;
}

// Fill in what an older or hand-written configuration lacks, in place, so the editor can bind every field. A result
// sheet follows the control type (side main, or a / b with result types).
export function completeEmailConfig(email, controlType) {
  convertLegacyEmail(email, controlType);
  const defaults = defaultEmailConfig(controlType);
  for (const key of Object.keys(defaults)) {
    if (email[key] === undefined) {
      email[key] = defaults[key];
    }
  }
  const rec = controlType === "REC";
  email.files.forEach((file) => {
    if (file.name === undefined) file.name = null;
    if (file.attach === undefined) file.attach = true;
    if (!Array.isArray(file.sheets)) file.sheets = [];
    file.sheets.forEach((sheet) => {
      if (sheet.kind !== "sql") sheet.kind = "result";
      const template = sheet.kind === "sql" ? defaultSqlSheet() : defaultResultSheet(rec ? "a" : "main");
      for (const field of Object.keys(template)) {
        if (sheet[field] === undefined) sheet[field] = template[field];
      }
      if (sheet.kind === "result") {
        if (rec && !["a", "b"].includes(sheet.side)) sheet.side = "a";
        if (!rec) {
          sheet.side = "main";
          delete sheet.result_types;
        }
      }
    });
  });
  return email;
}

// The default names of a file's sheets (mailer.default_sheet_names): the control name (ANL/REP) or the side (REC),
// with the result types when they are not all the side saves; Free SQL sheets SQL, SQL 2, ...
export function defaultSheetNames(sheets, controlType, controlName, ruleConfig) {
  let sqlNumber = 0;
  return sheets.map((sheet) => {
    if (sheet.kind === "sql") {
      sqlNumber += 1;
      return sqlNumber === 1 ? "SQL" : "SQL " + sqlNumber;
    }
    if (controlType !== "REC") return (controlName || "").toUpperCase();
    const available = availableResultTypes(ruleConfig, sheet.side);
    const chosen = chosenResultTypes(sheet, ruleConfig);
    const side = String(sheet.side || "").toUpperCase();
    return chosen.length && chosen.length < available.length ? side + " " + chosen.join("+") : side;
  });
}

// The name of a sheet without the numbering of repeats (mailer.sheet_title): its own, else the default, 31 characters.
function baseSheetName(name, fallback) {
  const own = (name || "")
    .replace(/[[\]:*?/\\]/g, "_")
    .trim()
    .replace(/^'+|'+$/g, "")
    .slice(0, 31);
  return own || (fallback || "").slice(0, 31);
}

// The names the sheets of a file get in Excel (mailer.sheet_title): repeats numbered " (2)", case-insensitive.
export function effectiveSheetNames(sheets, controlType, controlName, ruleConfig) {
  const defaults = defaultSheetNames(sheets, controlType, controlName, ruleConfig);
  const taken = new Set();
  return sheets.map((sheet, index) => {
    const name = baseSheetName(sheet.name, defaults[index]);
    let title = name;
    for (let number = 2; taken.has(title.toLowerCase()); number++) {
      const suffix = ` (${number})`;
      title = name.slice(0, 31 - suffix.length) + suffix;
    }
    taken.add(title.toLowerCase());
    return title;
  });
}

// The file name used when none is set (mailer.attachment_name): <NAME>_<run from>[_<run to>], then _2, _3...
export function defaultFileName(index, controlName) {
  return (controlName || "<NAME>").toUpperCase() + "_<run from>[_<run to>]" + (index ? "_" + (index + 1) : "") + ".xlsx";
}

// The first problem of an enabled email configuration, or null: { message, file, sheet } with the indexes of the file
// and sheet it is in, when it is in one.
export function emailConfigProblem(email, { controlType, controlName, ruleConfig }) {
  const problem = (message, file = null, sheet = null) => ({ message, file, sheet });
  const recipients = [...email.to, ...email.cc, ...email.bcc];
  if (!email.to.length) {
    return problem("Please enter at least one email recipient (To).");
  }
  const invalid = recipients.filter((address) => !isEmailAddress(address));
  if (invalid.length) {
    return problem("Not an email address: " + invalid.join(", "));
  }
  if (!email.subject || !email.subject.trim()) {
    return problem("Please enter an email subject.");
  }
  if (email.send_when === "evaluate_sql" && !(email.evaluate_sql || "").trim()) {
    return problem("Please enter the Evaluate SQL of the email, or choose another 'Send when'.");
  }
  if (email.max_records != null && !(Number.isInteger(email.max_records) && email.max_records > 0)) {
    return problem("Max records must be a whole number greater than 0.");
  }
  if (email.send_when === "done_with_results" && !email.files.length) {
    return problem("'Done, with results' needs at least one file to count the results in. Add a file (its Attach may be off), or choose another 'Send when'.");
  }
  const fileNames = email.files.map((file) => (file.name || "").trim().replace(/\.xlsx$/i, "").trim().toLowerCase());
  for (const [fileIndex, file] of email.files.entries()) {
    const fileLabel = "File " + (fileIndex + 1);
    if (fileNames[fileIndex] && fileNames.indexOf(fileNames[fileIndex]) < fileIndex) {
      return problem(fileLabel + " has the same name as file " + (fileNames.indexOf(fileNames[fileIndex]) + 1) + ".", fileIndex);
    }
    if (!file.sheets.length) {
      return problem(fileLabel + " has no sheet. Add one, or remove the file.", fileIndex);
    }
    const defaults = defaultSheetNames(file.sheets, controlType, controlName, ruleConfig);
    const names = effectiveSheetNames(file.sheets, controlType, controlName, ruleConfig);
    const bases = file.sheets.map((sheet, index) => baseSheetName(sheet.name, defaults[index]).toLowerCase());
    for (const [sheetIndex, sheet] of file.sheets.entries()) {
      const sheetLabel = `${fileLabel}, sheet "${names[sheetIndex]}"`;
      if (sheet.name && SHEET_NAME_INVALID.test(sheet.name)) {
        return problem(sheetLabel + ": the name contains a character Excel does not allow: [ ] : * ? / \\", fileIndex, sheetIndex);
      }
      if (sheet.name && sheet.name.trim() && bases.some((base, index) => index !== sheetIndex && base === bases[sheetIndex])) {
        return problem(sheetLabel + ": another sheet of the file has this name.", fileIndex, sheetIndex);
      }
      if (sheet.kind === "sql" && !(sheet.query || "").trim()) {
        return problem(sheetLabel + ": please enter the query, or remove the sheet.", fileIndex, sheetIndex);
      }
      if (sheet.kind === "result" && controlType === "REC") {
        const available = availableResultTypes(ruleConfig, sheet.side);
        if (!available.length) {
          return problem(sheetLabel + ": side " + String(sheet.side).toUpperCase() + " saves no results. Pick the other side, or remove the sheet.", fileIndex, sheetIndex);
        }
        if (!(sheet.result_types || []).some((type) => available.includes(type))) {
          return problem(sheetLabel + ": please choose at least one result type the side saves.", fileIndex, sheetIndex);
        }
      }
    }
  }
  return null;
}

// What is being dragged in the Email tab: a sheet { file, index } or a file index; plain, set only during a drag.
export const emailDrag = { sheet: null, file: null };

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
