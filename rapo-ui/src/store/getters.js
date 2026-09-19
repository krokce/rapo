export default {
  getToken: (state) => state.tokenValue,
  getTokenIsValid: (state) => state.tokenIsValid,
  getSocketConnected: (state) => state.socketConnected,
  getSearch: (state) => state.search,
  getEnvVersion: (state) => state.envVersion,
  getEnvInfo: (state) => state.envInfo,
  getEnvParameters: (state) => state.envParameters,
  hideSearch: (state) => state.hideSearch,
  controlCatalogueById: (state) => (controlId) => state.controlCatalogue.find((item) => item.control_id === Number(controlId)),
};
