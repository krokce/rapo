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
    };
  },
  mutations: rootMutations,
  actions: rootActions,
  getters: rootGetters,
});

export default store;
