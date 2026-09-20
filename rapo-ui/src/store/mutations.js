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
    state.controlCatalogue = payload;
  },
  updateControlResults(state, payload) {
    state.controlResults = payload.runs;
    state.controlResultsDay = payload.date;
    state.serverToday = payload.today;
  },
  updateSchedulerStatus(state, payload) {
    state.schedulerStatus = payload;
  },
  updateSocketConnected(state, payload) {
    state.socketConnected = payload;
  },
  updateTokenValue(state, payload) {
    state.tokenValue = payload;
    state.tokenIsValid = Boolean(payload);
  },
};
