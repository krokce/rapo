import { createStore } from "vuex";
import rootMutations from "./mutations.js";
import rootActions from "./actions.js";
import rootGetters from "./getters.js";

const store = createStore({
  state() {
    return {
      search: "",
      controlCatalogue: [],
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
    };
  },
  mutations: rootMutations,
  actions: rootActions,
  getters: rootGetters,
});

export default store;
