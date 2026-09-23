// Rows of the big lists are read-only snapshots replaced wholesale on every fetch, so they are frozen: Vue then
// skips making thousands of rows deeply reactive.
const freezeRows = (rows) => Object.freeze(rows.map(Object.freeze));

export default {
  // have to be synchronous
  updateSearch(state, payload) {
    state.search = payload;
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
  updateControlCatalogue(state, payload) {
    state.controlCatalogue = freezeRows(payload);
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
    state.kpiTypes = payload;
  },
  updateSocketConnected(state, payload) {
    state.socketConnected = payload;
  },
  updateTokenValue(state, payload) {
    state.tokenValue = payload;
    state.tokenIsValid = Boolean(payload);
  },
};
