<template>
  <q-layout view="hHh Lpr lff" class="bg-grey-1 rounded-borders">
    <q-header elevated class="bg-white text-grey-8 q-py-xs" height-hint="58">
      <q-toolbar>
        <q-btn flat dense round @click="toggleLeftDrawer" aria-label="Menu" icon="fas fa-bars" />

        <q-btn flat no-caps no-wrap class="q-ml-xs" v-if="$q.screen.gt.xs" :to="{ name: 'dashboard' }">
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
          <q-btn aria-label="Clear search" class="YL__toolbar-input-btn" color="grey-3" text-color="grey-8" icon="fas fa-times" unelevated @click="updateSearch('')" />
        </div>

        <q-space class="col-2" />
        <q-btn round flat dense size="sm" :icon="themeInfo.icon" :aria-label="`Theme: ${themeInfo.label}`" @click="cycleTheme">
          <q-tooltip>Theme: {{ themeInfo.label }} (click for {{ nextThemeInfo.label.toLowerCase() }})</q-tooltip>
        </q-btn>
        <q-icon
          v-if="getTokenIsValid"
          name="fas fa-circle"
          size="8px"
          class="q-ml-sm"
          :color="getSocketConnected ? 'teal' : 'grey-5'">
          <q-tooltip>{{ getSocketConnected ? "Live updates on" : "Live updates offline, reconnecting..." }}</q-tooltip>
        </q-icon>
        <!-- Shown before the scheduler status is known (grey, Unknown). -->
        <q-btn aria-label="Scheduler"
          v-if="getTokenIsValid && $can('scheduler')"
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
        <!-- A dot on it tells that a metric of the instance health reached its warning (amber) or critical (red) level. -->
        <q-btn aria-label="Instance details" v-if="getTokenIsValid && $can('instance')" round flat dense size="sm" class="q-ml-sm" color="teal" icon="fas fa-plug fa-rotate-90" @click="showInstanceDialog">
          <span v-if="healthLevel" class="health-dot" :class="`health-dot-${healthLevel}`" />
          <q-tooltip>Connected &mdash; instance details{{ healthText }}</q-tooltip>
        </q-btn>
        <q-icon v-else-if="getTokenIsValid" name="fas fa-plug fa-rotate-90" size="18px" class="q-ml-sm" color="teal">
          <q-tooltip>Connected</q-tooltip>
        </q-icon>
        <q-icon v-else name="fas fa-plug fa-rotate-90" size="18px" class="q-ml-sm" color="red">
          <q-tooltip>Disconnected</q-tooltip>
        </q-icon>
        <!-- Who is signed in: the user of the token, or the master token of rapo.ini. An amber dot: the token expires soon. -->
        <q-btn v-if="getTokenIsValid && whoami" flat dense no-caps no-wrap class="q-ml-sm user-btn" aria-label="Signed in as">
          <q-avatar size="24px" color="blue-grey-6" text-color="white" class="user-avatar">
            <q-icon v-if="whoami.master" name="fas fa-key" size="11px" />
            <span v-else>{{ initials }}</span>
            <span v-if="expiresSoon" class="health-dot health-dot-warn" />
          </q-avatar>
          <span v-if="$q.screen.gt.sm" class="user-btn__name q-ml-sm">{{ signedInName }}</span>
          <q-menu anchor="bottom right" self="top right" class="user-menu">
            <div class="user-menu__head row no-wrap items-center">
              <q-avatar size="40px" color="blue-grey-6" text-color="white">
                <q-icon v-if="whoami.master" name="fas fa-key" size="18px" />
                <span v-else>{{ initials }}</span>
              </q-avatar>
              <div class="q-ml-md user-menu__who">
                <div class="user-menu__name">{{ signedInName }}</div>
                <template v-if="!whoami.master">
                  <div class="user-menu__caption ellipsis" :title="whoami.user_email">{{ whoami.user_email }}</div>
                  <div v-if="whoami.label" class="user-menu__token-label ellipsis" :title="whoami.label">{{ whoami.label }}</div>
                </template>
                <div v-else class="user-menu__caption">Set in rapo.ini</div>
              </div>
            </div>
            <q-separator />
            <div class="user-menu__section">
              <div class="user-menu__section-title">Access</div>
              <div v-if="whoami.master" class="user-menu__line">Everything, including Free SQL</div>
              <template v-else>
                <div v-if="signedInAccess.rows.length" class="user-menu__grid">
                  <template v-for="row in signedInAccess.rows" :key="row.area">
                    <span>{{ row.title }}</span>
                    <span class="level-pill" :class="`level-pill--${row.level}`">{{ row.label }}</span>
                  </template>
                </div>
                <div v-if="signedInAccess.none.length" class="user-menu__muted q-mt-xs">No access: {{ signedInAccess.none.join(", ") }}</div>
              </template>
            </div>
            <q-separator />
            <div class="user-menu__section">
              <div class="user-menu__section-title">Token</div>
              <div v-if="whoami.master" class="user-menu__line">
                <q-icon name="fas fa-infinity" size="12px" class="user-menu__icon" />Never expires &middot; changed only in rapo.ini
              </div>
              <template v-else>
                <div class="user-menu__line" :class="{ 'user-menu__line--warn': expiresSoon }">
                  <q-icon name="fas fa-hourglass-half" size="12px" class="user-menu__icon" />
                  <span>{{ expiryText }}</span>
                  <span v-if="whoami.expires_at" class="user-menu__muted q-ml-auto q-pl-md">{{ toDateTimeString(whoami.expires_at) }}</span>
                </div>
                <div v-if="whoami.free_sql" class="user-menu__line text-orange-10">
                  <q-icon name="fas fa-code" size="12px" class="user-menu__icon" />Free SQL allowed
                </div>
              </template>
            </div>
            <q-separator />
            <q-list dense class="q-py-xs">
              <!-- The API tokens of users are managed only with the master token, from its menu. -->
              <q-item v-if="whoami.master" clickable v-close-popup :to="{ name: 'tokens' }" :active="$route.name === 'tokens'" active-class="menu-link--active">
                <q-item-section avatar><q-icon name="fas fa-key" size="14px" /></q-item-section>
                <q-item-section>API tokens</q-item-section>
              </q-item>
              <!-- A user resets only the own token; the master token is changed in rapo.ini. -->
              <q-item v-else clickable v-close-popup @click="confirmResetToken">
                <q-item-section avatar><q-icon name="fas fa-sync-alt" size="14px" /></q-item-section>
                <q-item-section>Reset my token&hellip;</q-item-section>
              </q-item>
              <q-item clickable v-close-popup @click="disconnect">
                <q-item-section avatar><q-icon name="fas fa-sign-out-alt" size="14px" /></q-item-section>
                <q-item-section>Sign out</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
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
          <!-- active is passed explicitly, so an editor route highlights the list it belongs to. -->
          <q-item
            v-for="link in menuLinks"
            :key="link.text"
            v-ripple
            clickable
            :to="link.route"
            :active="isActiveLink(link)"
            active-class="menu-link--active"
            :class="{ 'q-mt-lg': link.gap }">
            <q-item-section avatar>
              <q-icon :color="isActiveLink(link) ? 'teal' : 'grey'" :name="link.icon" />
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
        <!-- The page's own padding is enough on a narrow screen. -->
        <div :class="{ 'q-ma-lg': $q.screen.gt.sm }">
          <q-banner v-if="expiryBanner" dense rounded class="q-mb-md bg-orange-1 text-orange-10">
            <template #avatar>
              <q-icon name="fas fa-hourglass-half" size="16px" />
            </template>
            {{ expiryBanner }}
          </q-banner>
          <!-- The list pages are kept alive, so going back to them shows their rows, filters and scroll at once. -->
          <router-view v-slot="{ Component }">
            <keep-alive :include="['ControlCatalogue', 'ControlResults', 'DashboardPage', 'DataAnalysis', 'DatasourceCatalogue', 'DiscrepancyAnalysis', 'FileResults']">
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </div>
      </q-page>
    </q-page-container>

    <q-dialog v-model="instanceDialog">
      <q-card style="width: 1100px; max-width: 95vw">
        <q-card-section class="q-pb-none">
          <div class="text-h6">Instance details</div>
          <q-banner v-if="configBanner" dense rounded inline-actions class="q-mt-sm" :class="configBanner.class">
            <template #avatar>
              <q-icon name="fas fa-exclamation-triangle" size="16px" />
            </template>
            {{ configBanner.text }}
            <template #action v-if="configBanner.reload">
              <q-btn flat dense label="Reload" :loading="reloadingConfig" @click="reloadConfig">
                <q-tooltip>Apply the changes that do not need a restart</q-tooltip>
              </q-btn>
            </template>
          </q-banner>
        </q-card-section>

        <q-tabs v-model="instanceTab" dense inline-label align="left" no-caps active-color="teal" indicator-color="teal" class="q-px-md text-grey-7">
          <q-tab name="configuration" icon="fas fa-sliders-h" label="Configuration" />
          <q-tab name="health-os" icon="fas fa-server" label="Health Rapo server" />
          <q-tab name="health-db" icon="fas fa-database" label="Health Database" />
        </q-tabs>
        <q-separator />

        <!-- Both health tabs share one InstanceHealth, so a switch between them reloads nothing; the tab has a fixed height
             that its charts fill. -->
        <q-card-section v-if="instanceTab.startsWith('health')" class="scroll" style="height: 70vh">
          <instance-health v-if="instanceDialog" :group="instanceTab === 'health-db' ? 'db' : 'os'" @navigate="instanceDialog = false" />
        </q-card-section>

        <q-card-section v-else class="scroll" style="max-height: 70vh">
          <config-catalogue v-if="instanceDialog" />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Close" v-close-popup />
          <q-btn color="negative" label="Disconnect" v-close-popup @click="disconnect" />
        </q-card-actions>
      </q-card>
    </q-dialog>
    <TokenRevealDialog ref="tokenReveal" />
  </q-layout>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import { api, notifyError, signOut } from "./api";
import { DATASOURCE_ICON, FILES_ICON, schedulerState } from "./constants";
import { liveRefetch } from "./socket";
import { THEMES, applyTheme, readTheme, saveTheme } from "./utils/theme";
import { HEALTH_TILES, LEVEL_TEXT, tileLevel } from "./utils/health";
import { toDateTimeString } from "./utils/format";
import { EXPIRY_WARNING_DAYS, LEVEL_LABELS, daysUntil, routeAllowed } from "./utils/scopes";
import InstanceHealth from "./components/health/InstanceHealth.vue";
import ConfigCatalogue from "./components/ConfigCatalogue.vue";
import TokenRevealDialog from "./components/TokenRevealDialog.vue";

// The titles of the scope areas (rapo/web/api/scopes.py AREAS), for the signed-in menu.
const AREA_TITLES = {
  dashboard: "Dashboard",
  runs: "Runs",
  data: "Data",
  controls: "Controls",
  kpis: "KPIs",
  scheduler: "Scheduler",
  datasources: "Datasources",
  files: "Files",
  instance: "Instance",
};

const THEME_INFO = {
  auto: { icon: "fas fa-adjust", label: "Automatic" },
  light: { icon: "fas fa-sun", label: "Light" },
  dark: { icon: "fas fa-moon", label: "Dark" },
};

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
  components: { ConfigCatalogue, InstanceHealth, TokenRevealDialog },
  data() {
    return {
      leftDrawerOpen: false,
      miniDrawer: readMiniDrawer(),
      theme: readTheme(),
      instanceDialog: false,
      instanceTab: "configuration",
      reloadingConfig: false,
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
    cycleTheme() {
      this.theme = THEMES[(THEMES.indexOf(this.theme) + 1) % THEMES.length];
      applyTheme(this.theme);
      saveTheme(this.theme);
    },
    toDateTimeString,
    isActiveLink(link) {
      return link.routes.includes(this.$route.name);
    },
    async reloadConfig() {
      this.reloadingConfig = true;
      try {
        const result = await api("reload-config", { method: "POST" });
        await this.updateEnvironment();
        const pending = result.restart_required.length;
        this.$q.notify({
          type: "positive",
          message: `rapo.ini reloaded: ${result.applied.length} option(s) applied` + (pending ? `, ${pending} need a restart` : ""),
        });
      } catch (error) {
        notifyError("Failed to reload rapo.ini.", error);
      } finally {
        this.reloadingConfig = false;
      }
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
    // The header dot follows the worst level of the instance health, pushed only when it changes ("health:level").
    startHealthUpdates() {
      const refresh = async () => {
        try {
          this.$store.commit("updateInstanceHealth", await api("get-instance-health", { params: { history: false }, loadingBar: false }));
        } catch (error) {
          this.$store.commit("updateInstanceHealth", null);
        }
      };
      this.stopHealthUpdates();
      this.stopHealthLive = liveRefetch("health:level", refresh, { interval: 2000 });
      refresh();
    },
    stopHealthUpdates() {
      if (this.stopHealthLive) {
        this.stopHealthLive();
        this.stopHealthLive = null;
      }
      this.$store.commit("updateInstanceHealth", null);
    },
    disconnect() {
      signOut();
    },
    // A new secret for the signed-in user token, scopes and expiry unchanged. This browser switches to it (the cookie
    // too, when the token was remembered; the socket reconnects with it), then it is shown once for scripts and other
    // browsers, which the old one signs out.
    confirmResetToken() {
      const until = this.whoami.expires_at ? `until ${toDateTimeString(this.whoami.expires_at)}` : "without end";
      this.$q
        .dialog({
          title: "Reset your API token?",
          message:
            `You get a new token with the same areas, valid ${until} as now. The current token stops working at once: ` +
            "other browsers and scripts using it are signed out and need the new one. This browser switches over by itself.",
          persistent: true,
          focus: "cancel",
          cancel: { flat: true, label: "Cancel" },
          ok: { unelevated: true, color: "negative", label: "Reset token" },
        })
        .onOk(async () => {
          try {
            const result = await api("reset-my-token", { method: "POST" });
            if (this.$q.cookies.has("rapo_token")) {
              this.$q.cookies.set("rapo_token", result.token, { sameSite: "Strict", expires: "365d" });
            }
            this.$store.commit("updateTokenValue", result.token);
            this.$refs.tokenReveal.open({ ...result, self: true });
          } catch (error) {
            notifyError("Token was not reset.", error);
          }
        });
    },
  },
  computed: {
    themeInfo() {
      return THEME_INFO[this.theme];
    },
    nextThemeInfo() {
      return THEME_INFO[THEMES[(THEMES.indexOf(this.theme) + 1) % THEMES.length]];
    },
    ...mapGetters([
      "getSearch",
      "getTokenIsValid",
      "getSocketConnected",
      "getEnvVersion",
      "getEnvInfo",
      "getEnvConfigChanges",
    ]),
    // get-instance-health without history: the worst level and the level of each rule, for the header dot.
    ...mapState(["schedulerStatus", "instanceDialogRequest", "whoami"]),
    signedInName() {
      return this.whoami.master ? "Master token" : this.whoami.user_name;
    },
    initials() {
      const words = (this.whoami.user_name || this.whoami.user_email || "?").split(/[\s@._-]+/).filter(Boolean);
      return words
        .slice(0, 2)
        .map((word) => word[0].toUpperCase())
        .join("");
    },
    // The areas the token reaches with their level, and the titles of those it does not reach.
    signedInAccess() {
      const scopes = this.whoami.scopes || {};
      const areas = Object.keys(AREA_TITLES);
      return {
        rows: areas
          .filter((area) => scopes[area] && scopes[area] !== "none")
          .map((area) => ({ area, title: AREA_TITLES[area], level: scopes[area], label: LEVEL_LABELS[scopes[area]] })),
        none: areas.filter((area) => !scopes[area] || scopes[area] === "none").map((area) => AREA_TITLES[area]),
      };
    },
    expiryDays() {
      return this.whoami && !this.whoami.master ? daysUntil(this.whoami.expires_at) : null;
    },
    expiresSoon() {
      return this.expiryDays !== null && this.expiryDays <= EXPIRY_WARNING_DAYS;
    },
    expiryText() {
      const days = this.expiryDays;
      if (days === null) {
        return "Never expires";
      }
      return days < 1 ? "Expires today" : days === 1 ? "Expires tomorrow" : `Expires in ${days} days`;
    },
    // A user token expiring within EXPIRY_WARNING_DAYS says so above every page.
    expiryBanner() {
      const days = this.expiryDays;
      if (!this.expiresSoon) {
        return null;
      }
      const when = days < 1 ? "today" : days === 1 ? "tomorrow" : `in ${days} days`;
      return `Your API token expires ${when} (${toDateTimeString(this.whoami.expires_at)}). Ask the Rapo administrator to extend it.`;
    },
    ...mapState({ health: "instanceHealth" }),
    // KPI types are only manageable where the RACS KPI tables are deployed, the same condition that gives the
    // control editor its KPIs tab. routes are the route names in which a link shows as active.
    menuLinks() {
      const links = [
        { icon: "fas fa-tachometer-alt", text: "Dashboard", route: "/dashboard", routes: ["dashboard"] },
        { icon: "fas fa-tasks", text: "Results", route: "/results", routes: ["results", "data-analysis", "discrepancy-analysis"], gap: true },
        { icon: "fas fa-chart-line", text: "Controls", route: "/controls", routes: ["controls", "edit-control"] },
      ];
      if (this.getEnvInfo && this.getEnvInfo.kpi_available) {
        links.push({ icon: "fas fa-calculator", text: "KPI types", route: "/kpi-types", routes: ["kpi-types", "edit-kpi-type"] });
      }
      links.push({ icon: "fas fa-clock", text: "Scheduler", route: "/scheduler", routes: ["scheduler"], gap: true });
      // PDI Core datasources, where their tables are readable; spaced from the lists of rapo's own objects.
      if (this.getEnvInfo && this.getEnvInfo.datasources_available) {
        links.push({ icon: FILES_ICON, text: "Files", route: "/files", routes: ["files", "files-log", "file-analysis"], gap: true });
        links.push({ icon: DATASOURCE_ICON, text: "Datasources", route: "/datasources", routes: ["datasources", "edit-datasource"] });
      }
      // A link shows only for a page the token may open.
      return links.filter((link) => routeAllowed(this.whoami, this.$router.resolve(link.route)));
    },
    healthLevel() {
      return this.health && this.health.enabled ? this.health.level : null;
    },
    // The tiles at their warning or critical level, named in the tooltip of the button.
    healthText() {
      if (!this.healthLevel) {
        return "";
      }
      const tiles = HEALTH_TILES.filter((tile) => tileLevel(tile, this.health.levels)).map((tile) => tile.title);
      return ` · ${LEVEL_TEXT[this.healthLevel]}: ${tiles.join(", ")}`;
    },
    schedulerStateInfo() {
      return schedulerState(this.schedulerStatus && this.schedulerStatus.state);
    },
    // The notice of rapo.ini changes on disk: Reload applies those that need no restart.
    configBanner() {
      const state = this.getEnvConfigChanges;
      if (!state) {
        return null;
      }
      if (state.error) {
        return { class: "bg-red-1 text-red-10", text: state.error, reload: false };
      }
      const changes = state.changes || [];
      if (!changes.length) {
        return null;
      }
      const restart = changes.filter((item) => item.restart).length;
      const hot = changes.length - restart;
      const text = hot
        ? `rapo.ini changed on disk: ${hot} option(s) can be applied now` + (restart ? `, ${restart} need a restart` : "")
        : `rapo.ini changed on disk: ${restart} option(s) apply only after a restart`;
      return { class: "bg-orange-1 text-orange-10", text, reload: hot > 0 && this.$can("instance", "edit") };
    },
    // The browser tab names the instance, e.g. "RAPO - AUT Dev".
    documentTitle() {
      // The page first (route meta.title), so tabs and history tell pages apart.
      const name = this.getTokenIsValid && this.getEnvInfo && this.getEnvInfo.instance_name;
      const app = name ? `RAPO - ${name}` : "RAPO";
      return this.$route.meta.title ? `${this.$route.meta.title} · ${app}` : app;
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
    // A page asks for Instance details on a tab (the Dashboard's health tiles).
    instanceDialogRequest(request) {
      if (request) {
        this.instanceTab = request.tab;
        this.showInstanceDialog();
      }
    },
    documentTitle: {
      immediate: true,
      handler(title) {
        document.title = title;
      },
    },
    // App is never remounted, the token becomes valid on connection and empty on sign out.
    getTokenIsValid: {
      immediate: true,
      handler(valid) {
        if (valid) {
          if (this.$can("scheduler") || this.$can("dashboard") || this.$can("runs") || this.$can("controls")) {
            this.startSchedulerUpdates();
          }
          if (this.$can("instance") || this.$can("dashboard")) {
            this.startHealthUpdates();
          }
        } else {
          this.stopSchedulerUpdates();
          this.stopHealthUpdates();
        }
      },
    },
  },
  unmounted() {
    this.stopSchedulerUpdates();
    this.stopHealthUpdates();
  },
};
</script>

<style lang="sass">
.YL

  &__toolbar-input-container
    min-width: 100px
    width: 45%
    max-width: 640px

  &__toolbar-input-btn
    border-radius: 0
    border-style: solid
    border-width: 1px 1px 1px 0
    border-color: var(--rapo-border-soft)
    max-width: 30px
    width: 100%

// The signed-in user's name stays on the avatar's line, cut with an ellipsis (the menu shows it whole).
.user-btn
  max-width: 200px

  .q-btn__content
    flex-wrap: nowrap

.user-btn__name
  overflow: hidden
  text-overflow: ellipsis
  white-space: nowrap
  min-width: 0
  font-size: 13px

.user-avatar
  font-size: 11px
  font-weight: 500

.user-menu
  width: 300px
  max-width: 95vw

.user-menu__head
  padding: 16px

.user-menu .q-item
  padding: 0 16px

.user-menu .q-item__section--avatar
  min-width: 30px

.user-menu__who
  min-width: 0

.user-menu__name
  font-size: 15px
  font-weight: 500

.user-menu__caption
  font-size: 12px
  color: var(--rapo-muted)

.user-menu__token-label
  display: inline-block
  max-width: 100%
  margin-top: 4px
  padding: 0 8px
  border-radius: 10px
  font-size: 11px
  line-height: 18px
  color: var(--rapo-strong)
  background: var(--rapo-surface-alt)
  border: 1px solid var(--rapo-border-soft)

.user-menu__section
  padding: 10px 16px 12px

.user-menu__section-title
  margin-bottom: 6px
  font-size: 11px
  font-weight: 600
  letter-spacing: 0.05em
  text-transform: uppercase
  color: var(--rapo-label)

.user-menu__grid
  display: grid
  grid-template-columns: 1fr auto
  gap: 4px 12px
  align-items: center
  font-size: 13px

.user-menu__line
  display: flex
  align-items: center
  font-size: 13px
  line-height: 22px

  &--warn
    color: var(--rapo-warn)

.user-menu__icon
  width: 14px
  margin-right: 8px
  color: var(--rapo-label)

.user-menu__line--warn .user-menu__icon
  color: inherit

.user-menu__muted
  font-size: 12px
  color: var(--rapo-muted)

// A token's level in an area: one teal scale, darker the more it allows.
.level-pill
  min-width: 64px
  padding: 0 8px
  border-radius: 10px
  font-size: 11px
  font-weight: 500
  line-height: 18px
  text-align: center

  &--view
    color: var(--rapo-teal)
    background: var(--rapo-teal-soft)
  &--operate
    color: var(--rapo-level-operate-text)
    background: var(--rapo-level-operate)
  &--edit
    color: var(--rapo-on-strong)
    background: var(--rapo-level-edit)

.menu-link--active
  color: var(--rapo-teal)
  background: var(--rapo-teal-soft)
  font-weight: 500

.health-dot
  position: absolute
  z-index: 1
  top: 0
  right: 0
  width: 8px
  height: 8px
  border-radius: 50%
  border: 1px solid var(--rapo-surface)

  &.health-dot-warn
    background: var(--rapo-warn)
  &.health-dot-crit
    background: var(--rapo-crit)

// A virtual-scroll table on a list page (utils/layout.js): as tall as its rows, but no taller than the rest of the
// page, where it scrolls instead, with its header kept in view.
.list-table
  flex: 0 1 auto
  min-height: 0

  thead th
    position: sticky
    top: 0
    z-index: 1
    background: var(--rapo-header)

.skeleton-row td
  height: 45px

// A page title row: its items are centered (the h2's rows are items-center), and so are the chips, badges and spinners
// inside each item, which would otherwise sit on the text baseline of the h2's tall line.
h2.row > div
  display: flex
  align-items: center

// A title followed by a smaller text only (the day of Results and Files, the dataset of Data analysis): both share the
// title's baseline, so that they end on one line; centered, the smaller text would sit higher. A title with a chip
// (the editors, a datasource's file log) stays centered, as a chip on the baseline would hang below the title.
h2.title-baseline > div:first-child,
h2.title-baseline > .page-subject
  align-self: baseline
</style>
