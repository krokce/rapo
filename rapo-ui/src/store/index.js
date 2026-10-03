import { createStore } from "vuex";
import rootMutations, { SEARCH_KEY } from "./mutations.js";
import rootActions from "./actions.js";
import rootGetters from "./getters.js";

// The header search is kept for the browser session, like the list pages' filters (mixins/persistFilters.js).
function savedSearch() {
  try {
    return sessionStorage.getItem(SEARCH_KEY) || "";
  } catch (error) {
    return "";
  }
}

const store = createStore({
  state() {
    return {
      search: savedSearch(),
      controlCatalogue: [],
      // Schema drift of the result tables by control_id (get-schema-drift), for the Controls list.
      schemaDrift: {},
      controlResults: [],
      controlResultsDay: null,
      serverToday: null,
      // The server's clock minus the browser's, as of the last get-control-runs (utils/clock.js).
      serverClockOffset: 0,
      tokenIsValid: false,
      tokenValue: "",
      socketConnected: false,
      envVersion: null,
      envInfo: null,
      envParameters: null,
      // Differences between the loaded rapo.ini and the file (get-config-changes), or { error } when unreadable.
      envConfigChanges: null,
      schedulerStatus: null,
      kpiTypes: [],
      // PDI Core datasources (get-ds-list), and the files waiting for them as last counted (get-ds-status).
      datasourceCatalogue: [],
      datasourceStatus: null,
      // The file log of one day as aggregates (get-files-day), and the lane locks of PDI Core (get-pdi-state).
      fileDay: null,
      // The database's clock (the file log's) minus the browser's, as of the last get-files-day (utils/clock.js).
      databaseClockOffset: 0,
      pdiState: null,
    };
  },
  mutations: rootMutations,
  actions: rootActions,
  getters: rootGetters,
});

export default store;
