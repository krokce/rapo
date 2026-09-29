// Rows of the big lists are read-only snapshots replaced wholesale on every fetch, so they are frozen: Vue then
// skips making thousands of rows deeply reactive.
const freezeRows = (rows) => Object.freeze(rows.map(Object.freeze));

// The session key of the header search, read back when the store is created (index.js).
export const SEARCH_KEY = "rapo_filters_search";

export default {
  // have to be synchronous
  updateSearch(state, payload) {
    state.search = payload;
    try {
      sessionStorage.setItem(SEARCH_KEY, payload || "");
    } catch (error) {
      // Not remembered, which is all a failure costs.
    }
  },
  updateEnvVersion(state, payload) {
    state.envVersion = payload;
  },
  updateEnvInfo(state, payload) {
    state.envInfo = payload;
  },
  updateEnvParameters(state, payload) {
    state.envParameters = payload;
  },
  updateEnvConfigChanges(state, payload) {
    state.envConfigChanges = payload;
  },
  updateControlCatalogue(state, payload) {
    state.controlCatalogue = freezeRows(payload);
  },
  updateSchemaDrift(state, payload) {
    state.schemaDrift = Object.freeze(payload);
  },
  updateControlResults(state, payload) {
    state.controlResults = freezeRows(payload.runs);
    state.controlResultsDay = payload.date;
    state.serverToday = payload.today;
  },
  updateSchedulerStatus(state, payload) {
    state.schedulerStatus = payload;
  },
  updateKpiTypes(state, payload) {
    state.kpiTypes = freezeRows(payload);
  },
  updateDatasourceCatalogue(state, payload) {
    state.datasourceCatalogue = freezeRows(payload);
  },
  updateDatasourceStatus(state, payload) {
    state.datasourceStatus = Object.freeze(payload);
  },
  updateFileDay(state, payload) {
    state.fileDay = Object.freeze(payload);
  },
  updatePdiState(state, payload) {
    state.pdiState = Object.freeze(payload);
  },
  updateSocketConnected(state, payload) {
    state.socketConnected = payload;
  },
  updateTokenValue(state, payload) {
    state.tokenValue = payload;
    state.tokenIsValid = Boolean(payload);
  },
};
