import { createRouter, createWebHistory } from "vue-router";
import ControlCatalogue from "./components/ControlCatalogue.vue";
import ControlResults from "./components/ControlResults.vue";
import DatasourceCatalogue from "./components/DatasourceCatalogue.vue";
import FileResults from "./components/FileResults.vue";
import KpiTypes from "./components/KpiTypes.vue";
import SchedulerPage from "./components/SchedulerPage.vue";
import TokenBox from "./components/TokenBox.vue";
import store from "./store";

// The editors and the file log are their own chunks (CodeMirror and the editor boxes leave the first load).
const router = createRouter({
  // Fixes issue with page router navigates to renders scrolled to the bottom
  scrollBehavior: (to, from, savedPosition) => {
    if (savedPosition) {
      return savedPosition;
    } else if (to.hash) {
      return {
        el: to.hash,
      };
    } else {
      return { top: 0 };
    }
  },
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/results" },
    {
      name: "controls",
      path: "/controls",
      component: ControlCatalogue,
    },
    {
      name: "results",
      path: "/results",
      component: ControlResults,
    },
    {
      // Its own chunk, so ECharts and the analysis components load only when a dataset is analysed.
      name: "data-analysis",
      path: "/analysis/:processId/:dataset",
      meta: { hideSearch: true },
      component: () => import(/* webpackChunkName: "analysis" */ "./components/analysis/DataAnalysis.vue"),
    },
    {
      // What sets a run's discrepancies apart from its normal records; in the analysis chunk.
      name: "discrepancy-analysis",
      path: "/discrepancy-analysis/:processId/:side",
      meta: { hideSearch: true },
      component: () => import(/* webpackChunkName: "analysis" */ "./components/analysis/DiscrepancyAnalysis.vue"),
    },
    {
      name: "scheduler",
      path: "/scheduler",
      meta: { hideSearch: true },
      component: SchedulerPage,
    },
    {
      name: "edit-control",
      path: "/edit-control/:controlId?",
      meta: { hideSearch: true },
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
      meta: { searchPlaceholder: "Search KPI code or description" },
      component: KpiTypes,
    },
    {
      name: "edit-kpi-type",
      path: "/edit-kpi-type/:kpiCode?",
      meta: { hideSearch: true },
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
      meta: { searchPlaceholder: "Search datasource" },
      component: FileResults,
    },
    {
      name: "files-log",
      path: "/files-log/:id",
      meta: { hideSearch: true },
      component: () => import(/* webpackChunkName: "file-log" */ "./components/FileLogPage.vue"),
      props: true,
    },
    {
      name: "datasources",
      path: "/datasources",
      meta: { searchPlaceholder: "Search datasource, directory or mask" },
      component: DatasourceCatalogue,
    },
    {
      name: "edit-datasource",
      path: "/edit-datasource/:id?",
      meta: { hideSearch: true },
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
      name: "token",
      path: "/token",
      meta: { hideSearch: true },
      component: TokenBox,
    },
    { path: "/:notfound(.*)", redirect: "/results" },
  ],
});

router.beforeEach(function (to, from, next) {
  if (!store.state.tokenIsValid && to.name !== "token") {
    next({ path: "/token", query: { redirect: to.fullPath } });
  } else {
    next();
  }
});

export default router;
