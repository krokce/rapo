import { createRouter, createWebHistory } from "vue-router";
import ControlCatalogue from "./components/ControlCatalogue.vue";
import ControlEdit from "./components/ControlEdit.vue";
import ControlResults from "./components/ControlResults.vue";
import TokenBox from "./components/TokenBox.vue";
import store from "./store";

const router = createRouter({
  // Fixes issue with page router navigates to renders scrolled to the bottom
  scrollBehavior: (to, from, savedPosition) => {
    if (savedPosition) {
      return savedPosition;
    } else if (to.hash) {
      return {
        selector: to.hash,
      };
    } else {
      return { top: 0 };
    }
  },
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/controls" },
    {
      name: "controls",
      path: "/controls",
      meta: { hideSearch: false },
      component: ControlCatalogue,
    },
    {
      name: "results",
      path: "/results",
      meta: { hideSearch: false },
      component: ControlResults,
    },
    {
      name: "edit-control",
      path: "/edit-control/:controlId?",
      meta: { hideSearch: true },
      component: ControlEdit,
      props: true,
      beforeEnter: (to, from, next) => {
        if (!to.params.controlId) {
          next({ path: "/controls" }); // Redirect to controls if controlId is undefined
        } else {
          next();
        }
      },
    },
    {
      name: "token",
      path: "/token",
      meta: { hideSearch: true },
      component: TokenBox,
    },
    { path: "/:notfound(.*)", redirect: "/controls" },
  ],
});

router.beforeEach(function (to, from, next) {
  if (!store.state.tokenIsValid && to.name !== "token") {
    next({ path: "/token", query: { redirect: to.fullPath } });
  } else {
    if (to.meta.hideSearch) {
      store.state.hideSearch = true;
    } else {
      store.state.hideSearch = false;
    }
    next();
  }
});

export default router;
