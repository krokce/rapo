// Actions on a single control run (a rapo_log row), shared by the Results page and the editor's run log.
// `run` needs control_name, control_type, process_id, date_from, date_to; `onDone` refreshes the caller's list.
import { Dialog, Notify } from "quasar";
import { api, notifyError } from "./api";
import store from "./store";
import { cascadeMessage, chainOf } from "./utils/schedule";
import { copyText, escapeHtml, toDateString, toDateTimeString } from "./utils/format";

// Resolves to false on cancel, otherwise to the selected options (an empty array when there are none).
function confirm(title, message, options) {
  return new Promise((resolve) => {
    Dialog.create({ title, message, options, cancel: true, persistent: true })
      .onOk((selected) => resolve(selected || []))
      .onCancel(() => {
        Notify.create({ message: "No action taken" });
        resolve(false);
      });
  });
}

function runLabel(run) {
  return `'${run.control_name} PID:${run.process_id}'`;
}

// The chain configuration lives in the catalogue, and this action is also reachable from the editor,
// where it may not be loaded yet.
async function chainOfRun(controlName) {
  if (!store.state.controlCatalogue.length) {
    try {
      await store.dispatch("updateControlCatalogue");
    } catch (error) {
      return { iterations: 0, cascade: [] };
    }
  }
  return chainOf(controlName, store.state.controlCatalogue);
}

// The iterations of a manual run are optional and off by default, so the confirmation offers them
// as a checkbox naming the dates they would run for, which the engine computes.
async function iterationOption(run, chain) {
  if (!chain.iterations) {
    return undefined;
  }
  let preview = [];
  try {
    preview = await api("iteration-preview", {
      params: { name: run.control_name, date_from: toDateTimeString(run.date_from), date_to: toDateTimeString(run.date_to) },
      loadingBar: false,
    });
  } catch (error) {
    preview = [];
  }
  const dates = preview
    .map((item) => {
      const from = toDateString(item.date_from);
      const to = toDateString(item.date_to);
      return from === to ? from : `${from} - ${to}`;
    })
    .join(", ");
  const label = `Run ${chain.iterations} iteration${chain.iterations > 1 ? "s" : ""}${dates ? ` (${dates})` : ""}`;
  return { type: "checkbox", model: [], items: [{ label, value: "iterations" }] };
}

export async function reRun(run, onDone) {
  const from = toDateString(run.date_from);
  const to = toDateString(run.date_to);
  const chain = await chainOfRun(run.control_name);
  const note = cascadeMessage(chain.cascade);
  const question = `Re-run for '${from}'${from !== to ? ` - '${to}'` : ""}?`;
  const selected = await confirm(run.control_name, note ? `${question} ${note}` : question, await iterationOption(run, chain));
  if (!selected) {
    return;
  }
  try {
    await api("run-control", {
      method: "POST",
      params: {
        name: run.control_name,
        date_from: toDateTimeString(run.date_from),
        date_to: toDateTimeString(run.date_to),
        iterations: selected.includes("iterations") ? "true" : null,
      },
    });
    Notify.create({ type: "positive", message: "Control " + run.control_name + " queued for execution" });
    onDone();
  } catch (error) {
    notifyError("Control " + run.control_name + " failed to start.", error);
  }
}

export async function cancelRun(run, onDone) {
  if (!(await confirm(run.control_name, "Do you really want to stop the execution of this control?"))) {
    return;
  }
  try {
    await api("cancel-control", { method: "POST", params: { id: run.process_id } });
    Notify.create({ type: "positive", message: `Control run ${runLabel(run)} was canceled` });
    onDone();
  } catch (error) {
    notifyError(`Stopping control run ${runLabel(run)} failed.`, error);
  }
}

export async function revokeRun(run, onDone) {
  if (!(await confirm(run.control_name, "Do you really want to revoke this control run?"))) {
    return;
  }
  try {
    await api("revoke-control-run", { method: "DELETE", params: { id: run.process_id } });
    Notify.create({ type: "positive", message: `Control run ${runLabel(run)} was revoked` });
    onDone();
  } catch (error) {
    notifyError(`Revoke of control run ${runLabel(run)} failed.`, error);
  }
}

export async function dropTemporaryTables(run) {
  if (!(await confirm(run.control_name, `Do you really want to drop all debug temporary tables for execution with PID: ${run.process_id} ?`))) {
    return;
  }
  try {
    await api("delete-control-temporary-tables", { method: "DELETE", params: { id: run.process_id } });
    Notify.create({ type: "positive", message: `All temporary tables for PID:${run.process_id} were deleted` });
  } catch (error) {
    notifyError(`Temporary tables deletion for PID:${run.process_id} failed.`, error);
  }
}

export function showText(title, text) {
  Dialog.create({
    title,
    message: `<pre class="text-body2" style="white-space: pre-wrap;">${escapeHtml(text)}</pre>`,
    html: true,
    style: { width: "800px", maxWidth: "90vw" },
  });
}

export function showErrorLog(run) {
  showText(run.control_name + " - Error log", run.text_error || "No error log available");
}

export async function copySql(statement, description) {
  try {
    await copyText(statement);
    Notify.create({ type: "positive", message: `${description} SQL statement copied to clipboard: ${statement}` });
  } catch (error) {
    notifyError("Failed to copy SQL to clipboard.", error);
  }
}

// Results are in RAPO_REST_<name>, or RAPO_RESA_/RAPO_RESB_<name> per side for reconciliations.
export function copyResultsSql(run, side) {
  const suffix = run.control_type === "REC" ? side : "T";
  const statement = `select * from RAPO_RES${suffix}_${run.control_name} where RAPO_PROCESS_ID = ${run.process_id};`;
  return copySql(statement, `Discrepancies ${suffix === "T" ? "A" : side}-side`);
}
