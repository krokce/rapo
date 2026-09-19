import { api } from "../api";

export default {
  async updateControlCatalogue(context) {
    const data = await api("get-all-controls");
    context.commit("updateControlCatalogue", data);
    return data;
  },
  async updateControlResults(context) {
    const data = await api("get-control-runs");
    context.commit("updateControlResults", data);
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
