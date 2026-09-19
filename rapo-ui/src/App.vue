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
          <q-input dense outlined square v-model="search" placeholder="Search control name" class="bg-white col" />
          <q-btn class="YL__toolbar-input-btn" color="grey-3" text-color="grey-8" icon="close" unelevated @click="updateSearch('')" />
        </div>

        <q-space class="col-2" />
        <span class="text-caption text-weight-light text-teal" v-if="getTokenIsValid">Connected</span>
        <span class="text-caption text-weight-light text-red" v-if="!getTokenIsValid">Disconnected</span>
        <q-icon
          v-if="getTokenIsValid"
          name="fas fa-circle"
          size="8px"
          class="q-ml-sm"
          :color="getSocketConnected ? 'teal' : 'grey-5'">
          <q-tooltip>{{ getSocketConnected ? "Live updates on" : "Live updates offline, reconnecting..." }}</q-tooltip>
        </q-icon>
        <q-btn round flat color="teal" icon="fas fa-plug fa-rotate-90" @click="showDisconnectDialog" v-if="getTokenIsValid" />
      </q-toolbar>
    </q-header>

    <q-drawer v-model="leftDrawerOpen" show-if-above bordered class="bg-grey-2" :width="170" :breakpoint="500" v-if="getTokenIsValid">
      <q-scroll-area class="fit">
        <q-list padding class="menu-list">
          <q-item v-for="link in menuLinks" :key="link.text" v-ripple clickable :to="link.route">
            <q-item-section avatar>
              <q-icon color="grey" :name="link.icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ link.text }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </q-scroll-area>
    </q-drawer>

    <q-page-container>
      <q-page padding>
        <div class="q-ma-lg">
          <router-view></router-view>
        </div>
      </q-page>
    </q-page-container>

    <q-dialog v-model="instanceDialog" @hide="stopSchedulerUpdates">
      <q-card style="width: 560px; max-width: 90vw">
        <q-card-section class="text-h6">Instance details</q-card-section>

        <q-card-section class="q-pt-none scroll" style="max-height: 65vh">
          <div class="text-weight-bold q-mb-xs">Scheduler</div>
          <div v-if="schedulerStatus" class="q-mb-sm">
            <div class="row items-center q-gutter-sm">
              <q-chip text-color="white" :color="schedulerStateInfo.color" class="text-weight-bold q-ml-none">{{ schedulerStateInfo.label }}</q-chip>
              <small class="col text-grey-7">{{ schedulerStateInfo.description }}</small>
            </div>
            <table class="env-table">
              <tr>
                <td>Scheduling server</td>
                <td>
                  <strong>{{ schedulerStatus.holder.server || "N/A" }}{{ schedulerStatus.holder.pid ? " PID " + schedulerStatus.holder.pid : "" }}</strong>
                </td>
              </tr>
              <tr>
                <td>Heartbeat</td>
                <td>
                  <strong>{{ toDateTimeString(schedulerStatus.holder.heartbeat) || "N/A" }}</strong>
                </td>
              </tr>
              <tr>
                <td>Runs on this server</td>
                <td>
                  <strong>{{ schedulerStatus.runner.running.length }} running, {{ schedulerStatus.runner.queued.length }} queued</strong>
                </td>
              </tr>
            </table>
            <div class="row items-center q-gutter-sm q-mt-sm">
              <scheduler-toggle-button />
              <q-btn flat no-caps color="teal" icon="fas fa-clock" label="Open scheduler" :to="{ name: 'scheduler' }" v-close-popup />
            </div>
          </div>
          <div v-else class="text-grey-7 q-mb-sm">Loading...</div>
          <q-separator />

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
import SchedulerToggleButton from "./components/SchedulerToggleButton.vue";
import { notifyError, signOut } from "./api";
import { schedulerState } from "./constants";
import { liveRefetch } from "./socket";
import { toDateTimeString } from "./utils/format";

export default {
  components: {
    SchedulerToggleButton,
  },
  data() {
    return {
      leftDrawerOpen: false,
      instanceDialog: false,
      menuLinks: [
        {
          icon: "fas fa-chart-line",
          text: "Controls",
          route: "/controls",
        },
        {
          icon: "fas fa-tasks",
          text: "Results",
          route: "/results",
        },
        {
          icon: "fas fa-clock",
          text: "Scheduler",
          route: "/scheduler",
        },
      ],
    };
  },
  methods: {
    ...mapActions(["updateSearch", "updateSchedulerStatus"]),
    toDateTimeString,
    toggleLeftDrawer() {
      this.leftDrawerOpen = !this.leftDrawerOpen;
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
    showDisconnectDialog() {
      this.instanceDialog = true;
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
    schedulerStateInfo() {
      return schedulerState(this.schedulerStatus && this.schedulerStatus.state);
    },
    envSections() {
      return [
        { title: "Version", entries: this.flattenEntries(this.getEnvVersion) },
        { title: "Info", entries: this.flattenEntries(this.getEnvInfo) },
        { title: "Parameters", entries: this.flattenEntries(this.getEnvParameters) },
      ];
    },
    // Pages without a global search (editor, token page) set meta.hideSearch on their route.
    hideSearch() {
      return Boolean(this.$route.meta.hideSearch);
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
</style>
