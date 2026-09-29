// Actions on a single control run (a rapo_log row), shared by the Results page and the editor's run log.
// `run` needs control_name, control_type, process_id, date_from, date_to; `onDone` refreshes the caller's list.
import { Dialog, Notify } from "quasar";
import { api, notifyError } from "./api";
import store from "./store";
import { cascadeMessage, chainOf } from "./utils/schedule";
import { upstreamMessage } from "./utils/chain";
import { copyText, toDateString, toDateTimeString } from "./utils/format";

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
      return { iterations: 0, cascade: [], upstream: [] };
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
  const note = [upstreamMessage(chain.upstream), cascadeMessage(chain.cascade)].filter(Boolean).join(" ");
  const question = `Re-run for '${from}'${from !== to ? ` - '${to}'` : ""}?`;
  const selected = await confirm(run.control_name, note ? `${question} ${note}` : question, await iterationOption(run, chain));
  if (!selected) {
    return;
  }
  if (
    await startRun({
      name: run.control_name,
      date_from: toDateTimeString(run.date_from),
      date_to: toDateTimeString(run.date_to),
      iterations: selected.includes("iterations") ? "true" : null,
    })
  ) {
    onDone();
  }
}

// Queues a run (`params`: name, the window, debug_mode, iterations) and says so; false when the server refused it.
export async function startRun(params) {
  try {
    await api("run-control", { method: "POST", params });
  } catch (error) {
    notifyError("Control " + params.name + " failed to start.", error);
    return false;
  }
  Notify.create({ type: "positive", message: "Control " + params.name + " queued for execution" });
  return true;
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

// Sends the email of a finished run again, with the control's current email configuration.
export async function sendEmail(run) {
  if (!(await confirm(run.control_name, `Send the email of run PID:${run.process_id} again, with the current email configuration?`))) {
    return;
  }
  try {
    await api("send-control-email", { method: "POST", params: { process_id: run.process_id } });
    Notify.create({ type: "positive", message: `Email of control run ${runLabel(run)} was sent` });
  } catch (error) {
    notifyError(`Email of control run ${runLabel(run)} was not sent.`, error);
  }
}

// Copies text to the clipboard and says so; `what` reads "<what> copied to clipboard", `failure` is the error prefix.
export async function copyAndNotify(text, what, failure) {
  try {
    await copyText(text);
    Notify.create({ type: "positive", message: `${what} copied to clipboard` });
  } catch (error) {
    notifyError(failure, error);
  }
}

// The SQL of the records behind a number of a run (fetched_a|b, result_a|b), built by the server: a fetched dataset
// is the engine's select for the run's window, which only the engine can build.
export async function copyDatasetSql(run, dataset, label) {
  try {
    const { sql } = await api("get-run-dataset-sql", { params: { process_id: run.process_id, dataset } });
    await copyAndNotify(sql, `${label} SQL statement`, "Failed to copy SQL to clipboard.");
  } catch (error) {
    notifyError("Failed to copy SQL to clipboard.", error);
  }
}
