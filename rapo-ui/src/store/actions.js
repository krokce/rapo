import { api } from "../api";

// Sequence of get-control-runs requests, so a slow response for a previous day can't overwrite a newer one.
let controlResultsRequest = 0;

export default {
  async updateControlCatalogue(context) {
    const data = await api("get-all-controls");
    context.commit("updateControlCatalogue", data);
    return data;
  },
  // A dictionary-only check of every control's result tables: cheap, but not free, so it has no loading bar and
  // is refreshed on demand rather than with every catalogue fetch.
  async updateSchemaDrift(context) {
    const data = await api("get-schema-drift", { loadingBar: false });
    context.commit("updateSchemaDrift", data);
    return data;
  },
  // Runs started on one day (YYYY-MM-DD, default: the server's today).
  async updateControlResults(context, day = null) {
    const request = ++controlResultsRequest;
    const data = await api("get-control-runs", { params: { date: day } });
    if (request === controlResultsRequest) {
      context.commit("updateControlResults", data);
    }
    return data;
  },
  // Instance details shown in the header and the "Instance details" dialog.
  // An unreadable rapo.ini is kept as the error of the changes, so the rest of the details still show.
  async updateEnvironment(context) {
    const [version, info, parameters, changes] = await Promise.all([
      api("version"),
      api("info"),
      api("parameters"),
      api("get-config-changes").catch((error) => ({ changes: [], error: error.message })),
    ]);
    context.commit("updateEnvVersion", version);
    context.commit("updateEnvInfo", info);
    context.commit("updateEnvParameters", parameters);
    context.commit("updateEnvConfigChanges", changes);
  },
  // Scheduler and run manager state shown on the Scheduler page and in the "Instance details" dialog.
  async updateSchedulerStatus(context) {
    const data = await api("scheduler-status", { loadingBar: false });
    context.commit("updateSchedulerStatus", data);
    return data;
  },
  // Reference catalogue of KPI types. Empty when the RACS KPI tables are not deployed, which is also what
  // hides the KPIs tab of the control editor. Force is for the KPI types page, which edits the catalogue:
  // without it the first snapshot of the session would keep being served to every reader of it.
  async updateKpiTypes(context, { force = false } = {}) {
    if (!force && context.state.kpiTypes.length > 0) {
      return context.state.kpiTypes;
    }
    const data = await api("get-kpi-types", { loadingBar: false });
    context.commit("updateKpiTypes", data);
    return data;
  },
  updateSearch(context, payload) {
    context.commit("updateSearch", payload);
  },
  // Uses the candidate token rather than the stored one, so it can't go through api().
  async validateToken(context, token) {
    const response = await fetch("/api/help", { headers: { Authorization: `Bearer ${token}` } });
    context.commit("updateTokenValue", response.ok ? token : "");
    return response.ok;
  },
};
