import { createStore } from "vuex";
import rootMutations from "./mutations.js";
import rootActions from "./actions.js";
import rootGetters from "./getters.js";

const store = createStore({
  state() {
    return {
      search: "",
      hideSearch: false,
      controlCatalogue: [],
      controlResults: [],
      tokenIsValid: false,
      tokenValue: "",
      envVersion: null,
      envInfo: null,
      envParameters: null,
    };
  },
  mutations: rootMutations,
  actions: rootActions,
  getters: rootGetters,
});

export default store;
