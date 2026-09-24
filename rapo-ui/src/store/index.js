import { createStore } from "vuex";
import rootMutations from "./mutations.js";
import rootActions from "./actions.js";
import rootGetters from "./getters.js";

const store = createStore({
  state() {
    return {
      search: "",
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
      schedulerStatus: null,
      kpiTypes: [],
    };
  },
  mutations: rootMutations,
  actions: rootActions,
  getters: rootGetters,
});

export default store;
