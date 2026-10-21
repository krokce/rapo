import { createRouter, createWebHistory } from "vue-router";
import ControlCatalogue from "./components/ControlCatalogue.vue";
import ControlResults from "./components/ControlResults.vue";
import DatasourceCatalogue from "./components/DatasourceCatalogue.vue";
import FileResults from "./components/FileResults.vue";
import KpiTypes from "./components/KpiTypes.vue";
import SchedulerPage from "./components/SchedulerPage.vue";
import TokenBox from "./components/TokenBox.vue";
import { Cookies } from "quasar";
import store from "./store";
import { routeAllowed } from "./utils/scopes";

// The editors and the file log are their own chunks (CodeMirror and the editor boxes leave the first load).
const router = createRouter({
  // Back and forward return to where the page was; another page opens at its top. A page that only changes its query or
  // hash (a view kept in the URL) stays where it is, and one opened with a hash (the analysis pages' sections) scrolls
  // there itself once its content is loaded.
  scrollBehavior: (to, from, savedPosition) => {
    if (savedPosition) {
      return savedPosition;
    }
    if (to.hash || to.path === from.path) {
      return false;
    }
    return { top: 0 };
  },
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    {
      // Its own chunk, which loads ECharts (shared with the analysis pages) only once the page is open.
      name: "dashboard",
      path: "/dashboard",
      meta: { scope: ["dashboard", "view"], hideSearch: true },
      component: () => import(/* webpackChunkName: "dashboard" */ "./components/dashboard/DashboardPage.vue"),
    },
    {
      name: "controls",
      meta: { scope: ["controls", "view"] },
      path: "/controls",
      component: ControlCatalogue,
    },
    {
      name: "results",
      path: "/results",
      component: ControlResults,
      meta: { scope: ["runs", "view"], searchPlaceholder: "Search control name or process ID" },
    },
    {
      // The records a file of the PDI Core file log loaded into a table of its datasource (FILE_ID), on the same page.
      name: "file-analysis",
      path: "/analysis/file/:fileId/:table",
      meta: { scope: ["data", "view"], hideSearch: true },
      component: () => import(/* webpackChunkName: "analysis" */ "./components/analysis/DataAnalysis.vue"),
    },
    {
      // Its own chunk, so ECharts and the analysis components load only when a dataset is analysed.
      name: "data-analysis",
      path: "/analysis/:processId/:dataset",
      meta: { scope: ["data", "view"], hideSearch: true },
      component: () => import(/* webpackChunkName: "analysis" */ "./components/analysis/DataAnalysis.vue"),
    },
    {
      // What sets a run's discrepancies apart from its normal records; in the analysis chunk.
      name: "discrepancy-analysis",
      path: "/discrepancy-analysis/:processId/:side",
      meta: { scope: ["data", "view"], hideSearch: true },
      component: () => import(/* webpackChunkName: "analysis" */ "./components/analysis/DiscrepancyAnalysis.vue"),
    },
    {
      name: "scheduler",
      path: "/scheduler",
      meta: { scope: ["scheduler", "view"], searchPlaceholder: "Search control name or process ID" },
      component: SchedulerPage,
    },
    {
      name: "edit-control",
      path: "/edit-control/:controlId?",
      meta: { scope: ["controls", "view"], hideSearch: true },
      component: () => import(/* webpackChunkName: "control-editor" */ "./components/ControlEdit.vue"),
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
      name: "kpi-types",
      path: "/kpi-types",
      meta: { scope: ["kpis", "view"], searchPlaceholder: "Search KPI code or description" },
      component: KpiTypes,
    },
    {
      name: "edit-kpi-type",
      path: "/edit-kpi-type/:kpiCode?",
      meta: { scope: ["kpis", "view"], hideSearch: true },
      component: () => import(/* webpackChunkName: "kpi-type-editor" */ "./components/EditKpiType.vue"),
      props: true,
      beforeEnter: (to, from, next) => {
        if (!to.params.kpiCode) {
          next({ path: "/kpi-types" }); // Redirect to the catalogue if kpiCode is undefined
        } else {
          next();
        }
      },
    },
    {
      name: "files",
      path: "/files",
      meta: { scope: ["files", "view"], searchPlaceholder: "Search datasource name or ID, ?file name, #file ID" },
      component: FileResults,
    },
    {
      name: "files-log",
      path: "/files-log/:id",
      meta: { scope: ["files", "view"], searchPlaceholder: "Search file name, ?name prefix, #file ID" },
      component: () => import(/* webpackChunkName: "file-log" */ "./components/FileLogPage.vue"),
      props: true,
    },
    {
      name: "datasources",
      path: "/datasources",
      meta: { scope: ["datasources", "view"], searchPlaceholder: "Search datasource, directory or mask" },
      component: DatasourceCatalogue,
    },
    {
      name: "edit-datasource",
      path: "/edit-datasource/:id?",
      meta: { scope: ["datasources", "view"], hideSearch: true },
      component: () => import(/* webpackChunkName: "datasource-editor" */ "./components/EditDatasource.vue"),
      props: true,
      beforeEnter: (to, from, next) => {
        if (!to.params.id) {
          next({ path: "/datasources" }); // Redirect to the list if id is undefined
        } else {
          next();
        }
      },
    },
    {
      // The API tokens of users, for the master token only.
      name: "tokens",
      path: "/tokens",
      meta: { master: true, searchPlaceholder: "Search name, email or label" },
      component: () => import(/* webpackChunkName: "tokens" */ "./components/TokensPage.vue"),
    },
    {
      name: "token",
      path: "/token",
      meta: { hideSearch: true },
      component: TokenBox,
    },
    { path: "/:notfound(.*)", redirect: "/dashboard" },
  ],
});

// The pages in the order a token without the Dashboard is sent to the first it may open.
const LANDING_PAGES = ["dashboard", "results", "controls", "kpi-types", "scheduler", "files", "datasources"];

router.beforeEach(function (to, from, next) {
  if (!store.state.tokenIsValid && to.name !== "token") {
    next({ path: "/token", query: { redirect: to.fullPath } });
    return;
  }
  const whoami = store.state.whoami;
  if (to.name === "token" || routeAllowed(whoami, to)) {
    next();
    return;
  }
  const landing = LANDING_PAGES.map((name) => router.resolve({ name })).find((route) => routeAllowed(whoami, route));
  if (landing) {
    next({ name: landing.name, replace: true });
  } else {
    // A token that opens no page at all: back to the token page, without signing in again by the remembered cookie.
    Cookies.remove("rapo_token");
    store.commit("updateTokenValue", "");
    next({ path: "/token", query: { denied: "1" } });
  }
});

// A page of an older build asks for chunks the server no longer has (they are named by their content): the app is
// loaded anew on the page it was going to.
router.onError((error, to) => {
  if (error && (error.name === "ChunkLoadError" || /Loading (CSS )?chunk/.test(error.message || ""))) {
    window.location.assign(to && to.fullPath ? to.fullPath : window.location.href);
  }
});

export default router;
