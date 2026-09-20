import { api } from "../api";

// Sequence of get-control-runs requests, so a slow response for a previous day can't overwrite a newer one.
let controlResultsRequest = 0;

export default {
  async updateControlCatalogue(context) {
    const data = await api("get-all-controls");
    context.commit("updateControlCatalogue", data);
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
  async updateEnvironment(context) {
    const [version, info, parameters] = await Promise.all([api("version"), api("info"), api("parameters")]);
    context.commit("updateEnvVersion", version);
    context.commit("updateEnvInfo", info);
    context.commit("updateEnvParameters", parameters);
  },
  // Scheduler and run manager state shown on the Scheduler page and in the "Instance details" dialog.
  async updateSchedulerStatus(context) {
    const data = await api("scheduler-status", { loadingBar: false });
    context.commit("updateSchedulerStatus", data);
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
