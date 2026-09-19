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
  updateHideSearch(state, payload) {
    state.hideSearch = payload;
  },
  updateControlCatalogue(state, payload) {
    state.controlCatalogue = payload;
  },
  updateControlResults(state, payload) {
    state.controlResults = payload;
  },
  updateTokenValue(state, payload) {
    state.tokenValue = payload;
    if (payload) {
      state.tokenIsValid = true;
    }
    else {
      state.tokenIsValid = false;
    }
  },
};
