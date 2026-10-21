import { api } from "../api";

// Sequence of get-control-runs requests, so a slow response for a previous day can't overwrite a newer one.
let controlResultsRequest = 0;
// The same for get-files-day.
let fileDayRequest = 0;
// The same for get-schema-drift, whose answer may take seconds: a slow one must not bring back a fixed drift.
let schemaDriftRequest = 0;

export default {
  async updateControlCatalogue(context) {
    const data = await api("get-all-controls");
    context.commit("updateControlCatalogue", data);
    return data;
  },
  // A dictionary-only check of every control's result tables: cheap, but not free, so it has no loading bar and
  // is refreshed on demand rather than with every catalogue fetch.
  async updateSchemaDrift(context) {
    const request = ++schemaDriftRequest;
    const data = await api("get-schema-drift", { loadingBar: false });
    if (request === schemaDriftRequest) {
      context.commit("updateSchemaDrift", data);
    }
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
  // rapo.ini and its changes are read only by a token that may view the instance.
  async updateEnvironment(context) {
    const instance = context.getters.can("instance", "view");
    const [version, info, parameters, changes] = await Promise.all([
      api("version"),
      api("info"),
      instance ? api("parameters") : null,
      instance ? api("get-config-changes").catch((error) => ({ changes: [], error: error.message })) : null,
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
  async updateDatasourceCatalogue(context) {
    const data = await api("get-ds-list");
    context.commit("updateDatasourceCatalogue", data);
    return data;
  },
  // Counted by the server in the background (pending before its first count), so it has no loading bar.
  async updateDatasourceStatus(context) {
    const data = await api("get-ds-status", { loadingBar: false });
    context.commit("updateDatasourceStatus", data);
    return data;
  },
  // The file log of one day (YYYY-MM-DD, default: the database's today) as aggregates.
  async updateFileDay(context, day = null) {
    const request = ++fileDayRequest;
    const data = await api("get-files-day", { params: { date: day } });
    if (request === fileDayRequest) {
      context.commit("updateFileDay", data);
    }
    return data;
  },
  async updatePdiState(context) {
    const data = await api("get-pdi-state", { loadingBar: false });
    context.commit("updatePdiState", data);
    return data;
  },
  updateSearch(context, payload) {
    context.commit("updateSearch", payload);
  },
  // The signed-in token's scopes, read again after a reconnection; a revoked token answers 401, which signs out.
  async refreshWhoami(context) {
    context.commit("updateWhoami", await api("whoami", { loadingBar: false }));
  },
  // Uses the candidate token rather than the stored one, so it can't go through api().
  // whoami also says what the token may do, which the menu, the router and the pages follow.
  // A server error (the database failed to check a user token: 503) throws: the token was not rejected.
  async validateToken(context, token) {
    const response = await fetch("/api/whoami", { headers: { Authorization: `Bearer ${token}` } });
    if (response.status >= 500) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    context.commit("updateWhoami", response.ok ? await response.json() : null);
    context.commit("updateTokenValue", response.ok ? token : "");
    return response.ok;
  },
};
