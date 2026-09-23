<template>
  <q-layout view="hHh Lpr lff" class="bg-grey-1 rounded-borders">
    <q-header elevated class="bg-white text-grey-8 q-py-xs" height-hint="58">
      <q-toolbar>
        <q-btn flat dense round @click="toggleLeftDrawer" aria-label="Menu" icon="menu" />

        <q-btn flat no-caps no-wrap class="q-ml-xs" v-if="$q.screen.gt.xs" :to="{ name: 'controls' }">
          <q-icon name="fas fa-poll" color="teal" size="40px" />
          <q-toolbar-title shrink class="column text-left">
            <span class="text-weight-bold">Rapo</span>
            <span class="text-caption">
              {{ getEnvInfo && getEnvInfo.instance_name ? getEnvInfo.instance_name : "" }}
              {{ getEnvVersion && getEnvVersion.version ? "v." + getEnvVersion.version : "" }}
            </span>
          </q-toolbar-title>
        </q-btn>

        <q-space class="col-1" />

        <div class="YL__toolbar-input-container row no-wrap" v-if="!hideSearch">
          <q-input dense outlined square v-model="search" :placeholder="searchPlaceholder" class="bg-white col" />
          <q-btn class="YL__toolbar-input-btn" color="grey-3" text-color="grey-8" icon="close" unelevated @click="updateSearch('')" />
        </div>

        <q-space class="col-2" />
        <q-icon
          v-if="getTokenIsValid"
          name="fas fa-circle"
          size="8px"
          class="q-ml-sm"
          :color="getSocketConnected ? 'teal' : 'grey-5'">
          <q-tooltip>{{ getSocketConnected ? "Live updates on" : "Live updates offline, reconnecting..." }}</q-tooltip>
        </q-icon>
        <q-btn
          v-if="getTokenIsValid && schedulerStatus"
          round
          flat
          dense
          size="sm"
          class="q-ml-sm"
          :color="schedulerStateInfo.color"
          icon="fas fa-clock"
          :to="{ name: 'scheduler' }">
          <q-tooltip>Scheduler: {{ schedulerStateInfo.label }} &mdash; {{ schedulerStateInfo.description }}</q-tooltip>
        </q-btn>
        <!-- The color of the plug is the only sign of the connection: teal connected, red disconnected. -->
        <q-btn v-if="getTokenIsValid" round flat dense size="sm" class="q-ml-sm" color="teal" icon="fas fa-plug fa-rotate-90" @click="showInstanceDialog">
          <q-tooltip>Connected &mdash; instance details</q-tooltip>
        </q-btn>
        <q-icon v-else name="fas fa-plug fa-rotate-90" size="18px" class="q-ml-sm" color="red">
          <q-tooltip>Disconnected</q-tooltip>
        </q-icon>
      </q-toolbar>
    </q-header>

    <q-drawer
      v-model="leftDrawerOpen"
      show-if-above
      bordered
      class="bg-grey-2"
      :width="170"
      :mini="miniDrawer"
      :mini-width="60"
      :breakpoint="500"
      v-if="getTokenIsValid">
      <q-scroll-area class="fit">
        <q-list padding class="menu-list">
          <q-item v-for="link in menuLinks" :key="link.text" v-ripple clickable :to="link.route">
            <q-item-section avatar>
              <q-icon color="grey" :name="link.icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ link.text }}</q-item-label>
            </q-item-section>
            <q-tooltip v-if="miniDrawer" anchor="center right" self="center left" :offset="[8, 0]">{{ link.text }}</q-tooltip>
          </q-item>
        </q-list>
      </q-scroll-area>
    </q-drawer>

    <q-page-container>
      <q-page padding>
        <div class="q-ma-lg">
          <!-- The list pages are kept alive, so going back to them shows their rows, filters and scroll at once. -->
          <router-view v-slot="{ Component }">
            <keep-alive :include="['ControlCatalogue', 'ControlResults']">
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </div>
      </q-page>
    </q-page-container>

    <q-dialog v-model="instanceDialog">
      <q-card style="width: 560px; max-width: 90vw">
        <q-card-section class="q-pb-none">
          <div class="text-h6">Instance details</div>
          <div class="text-grey-7 instance-paths" v-if="getEnvInfo">
            <div v-if="getEnvInfo.config_path"><span>Configuration</span>{{ getEnvInfo.config_path }}</div>
            <div v-if="getEnvInfo.log_directory"><span>Logs</span>{{ getEnvInfo.log_directory }}</div>
          </div>
        </q-card-section>

        <q-card-section class="scroll" style="max-height: 65vh">
          <div v-for="section in envSections" :key="section.title" class="q-mt-sm">
            <div class="text-weight-bold q-mb-xs">{{ section.title }}</div>
            <table class="env-table">
              <colgroup>
                <col style="width: 70%" />
                <col style="width: 30%" />
              </colgroup>
              <tr v-if="!section.entries.length">
                <td colspan="2">N/A</td>
              </tr>
              <tr v-for="[key, value] in section.entries" :key="key">
                <td>{{ key }}</td>
                <td>
                  <strong>{{ value === null || value === undefined || value === "" ? "N/A" : String(value) }}</strong>
                </td>
              </tr>
            </table>
            <q-separator class="q-mt-sm" />
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Close" v-close-popup />
          <q-btn color="negative" label="Disconnect" v-close-popup @click="disconnect" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-layout>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import { notifyError, signOut } from "./api";
import { schedulerState } from "./constants";
import { liveRefetch } from "./socket";

// The drawer collapsed to its icons (the burger button), remembered by the browser across sessions.
const MINI_DRAWER_KEY = "rapo_mini_drawer";

function readMiniDrawer() {
  try {
    return localStorage.getItem(MINI_DRAWER_KEY) === "true";
  } catch (error) {
    return false;
  }
}

export default {
  data() {
    return {
      leftDrawerOpen: false,
      miniDrawer: readMiniDrawer(),
      instanceDialog: false,
    };
  },
  methods: {
    ...mapActions(["updateSearch", "updateSchedulerStatus", "updateEnvironment"]),
    // Collapses the drawer to its icons, or expands it back. Below the drawer breakpoint (500px), where the drawer
    // overlays the page and Quasar ignores mini, it opens and closes it instead.
    toggleLeftDrawer() {
      if (this.$q.screen.width < 500) {
        this.leftDrawerOpen = !this.leftDrawerOpen;
        return;
      }
      this.miniDrawer = !this.miniDrawer;
      try {
        localStorage.setItem(MINI_DRAWER_KEY, String(this.miniDrawer));
      } catch (error) {
        // Storage unavailable (private mode, blocked): the choice lasts for this page load only.
      }
    },
    flattenEntries(source, parentKey = "") {
      if (!source || typeof source !== "object") {
        return [];
      }

      return Object.entries(source).reduce((entries, [key, value]) => {
        const fullKey = parentKey ? `${parentKey}.${key}` : key;

        if (Array.isArray(value)) {
          if (!value.length) {
            entries.push([fullKey, "[]"]);
            return entries;
          }

          value.forEach((item, index) => {
            const itemKey = `${fullKey}[${index}]`;
            if (item !== null && typeof item === "object") {
              entries.push(...this.flattenEntries(item, itemKey));
            } else {
              entries.push([itemKey, item]);
            }
          });
          return entries;
        }

        if (value !== null && typeof value === "object") {
          const nestedEntries = this.flattenEntries(value, fullKey);
          if (!nestedEntries.length) {
            entries.push([fullKey, "{}"]);
            return entries;
          }
          entries.push(...nestedEntries);
          return entries;
        }

        entries.push([fullKey, value]);
        return entries;
      }, []);
    },
    showInstanceDialog() {
      this.instanceDialog = true;
      // The configuration of a restarted server may differ from the one read at connection time.
      this.updateEnvironment().catch((error) => notifyError("Failed to load instance details.", error));
    },
    // The scheduler state indicator of the header follows the scheduler as long as the user is connected.
    startSchedulerUpdates() {
      const refresh = () => this.updateSchedulerStatus().catch((error) => notifyError("Failed to load scheduler status.", error));
      this.stopSchedulerUpdates();
      this.stopLiveUpdates = liveRefetch("scheduler:changed", refresh, { interval: 2000 });
      refresh();
    },
    stopSchedulerUpdates() {
      if (this.stopLiveUpdates) {
        this.stopLiveUpdates();
        this.stopLiveUpdates = null;
      }
    },
    disconnect() {
      signOut();
    },
  },
  computed: {
    ...mapGetters(["getSearch", "getTokenIsValid", "getSocketConnected", "getEnvVersion", "getEnvInfo", "getEnvParameters"]),
    ...mapState(["schedulerStatus"]),
    // KPI types are only manageable where the RACS KPI tables are deployed, the same condition that gives the
    // control editor its KPIs tab.
    menuLinks() {
      const links = [
        { icon: "fas fa-chart-line", text: "Controls", route: "/controls" },
        { icon: "fas fa-tasks", text: "Results", route: "/results" },
        { icon: "fas fa-clock", text: "Scheduler", route: "/scheduler" },
      ];
      if (this.getEnvInfo && this.getEnvInfo.kpi_available) {
        links.push({ icon: "fas fa-calculator", text: "KPI types", route: "/kpi-types" });
      }
      return links;
    },
    schedulerStateInfo() {
      return schedulerState(this.schedulerStatus && this.schedulerStatus.state);
    },
    // The version of the application, then one section per section of rapo.ini.
    envSections() {
      return [
        { title: "Version", entries: this.flattenEntries(this.getEnvVersion) },
        ...Object.entries(this.getEnvParameters || {}).map(([title, values]) => ({ title, entries: this.flattenEntries(values) })),
      ];
    },
    // Pages without a global search (editor, token page) set meta.hideSearch on their route, and a page that
    // searches something else than controls sets meta.searchPlaceholder.
    hideSearch() {
      return Boolean(this.$route.meta.hideSearch);
    },
    searchPlaceholder() {
      return this.$route.meta.searchPlaceholder || "Search control name";
    },
    search: {
      get() {
        return this.getSearch;
      },
      set(value) {
        return this.updateSearch(value);
      },
    },
  },
  watch: {
    // App is never remounted, the token becomes valid on connection and empty on sign out.
    getTokenIsValid: {
      immediate: true,
      handler(valid) {
        if (valid) {
          this.startSchedulerUpdates();
        } else {
          this.stopSchedulerUpdates();
        }
      },
    },
  },
  unmounted() {
    this.stopSchedulerUpdates();
  },
};
</script>

<style lang="sass">
.YL

  &__toolbar-input-container
    min-width: 100px
    width: 55%

  &__toolbar-input-btn
    border-radius: 0
    border-style: solid
    border-width: 1px 1px 1px 0
    border-color: rgba(0,0,0,.24)
    max-width: 30px
    width: 100%

  &__drawer-footer-link
    color: inherit
    text-decoration: none
    font-weight: 500
    font-size: .75rem

    &:hover
      color: #000
.instance-paths
  font-family: Monospace, sans-serif
  font-size: 12px
  line-height: 1.5
  word-break: break-all

  span
    display: inline-block
    width: 100px

.env-table
  border-collapse: collapse
  width: 100%
  table-layout: fixed
  font-family: Monospace, sans-serif
  font-size: 12px
  line-height: 1.25

  td
    padding: 2px 10px 2px 0
    vertical-align: top
    word-break: break-word

// A virtual-scroll table on a list page (utils/layout.js): as tall as its rows, but no taller than the rest of the
// page, where it scrolls instead, with its header kept in view.
.list-table
  flex: 0 1 auto
  min-height: 0

  thead th
    position: sticky
    top: 0
    z-index: 1
    background: #cfd8dc

.skeleton-row td
  height: 45px
</style>
