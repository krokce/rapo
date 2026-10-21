import { allows, hasFreeSql } from "../utils/scopes";
export default {
  getToken: (state) => state.tokenValue,
  getTokenIsValid: (state) => state.tokenIsValid,
  // can(area, level): whether the signed-in token reaches that level (utils/scopes.js).
  can: (state) => (area, level) => allows(state.whoami, area, level),
  canFreeSql: (state) => hasFreeSql(state.whoami),
  isMaster: (state) => Boolean(state.whoami && state.whoami.master),
  getSocketConnected: (state) => state.socketConnected,
  getSearch: (state) => state.search,
  getEnvVersion: (state) => state.envVersion,
  getEnvInfo: (state) => state.envInfo,
  getEnvParameters: (state) => state.envParameters,
  getEnvConfigChanges: (state) => state.envConfigChanges,
  controlCatalogueById: (state) => (controlId) => state.controlCatalogue.find((item) => item.control_id === Number(controlId)),
  // Control IDs by name, built once per catalogue, for links to the controls a text names.
  controlIdsByName: (state) => new Map(state.controlCatalogue.map((item) => [item.control_name, item.control_id])),
};
