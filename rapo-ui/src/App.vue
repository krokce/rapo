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
          <q-input dense outlined square v-model="search" placeholder="Search control name" class="bg-white col" @keyup="updateSearch(search)" />
          <q-btn class="YL__toolbar-input-btn" color="grey-3" text-color="grey-8" icon="close" unelevated @click="updateSearch('')" />
        </div>

        <q-space class="col-2" />
        <span class="text-caption text-weight-light text-teal" v-if="getTokenIsValid">Connected</span>
        <span class="text-caption text-weight-light text-red" v-if="!getTokenIsValid">Disconnected</span>
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
  </q-layout>
</template>

<script>
import { mapActions, mapGetters } from "vuex";
import { useQuasar } from "quasar";

export default {
  data() {
    return {
      leftDrawerOpen: false,
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
      ],
      $q: useQuasar(),
    };
  },
  methods: {
    ...mapActions(["updateControlCatalogue", "updateSearch", "removeToken"]),
    toggleLeftDrawer() {
      this.leftDrawerOpen = !this.leftDrawerOpen;
    },
    escapeHtml(value) {
      return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
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
    createEnvSection(title, objectValue) {
      const entries = this.flattenEntries(objectValue);
      const rows = entries.length
        ? entries
            .map(([key, value]) => {
              const displayValue = value === null || value === undefined || value === "" ? "N/A" : String(value);
              return `<tr>
                <td style="padding:2px 10px 2px 0; vertical-align:top; word-break:break-word;">${this.escapeHtml(key)}</td>
                <td style="padding:2px 0; vertical-align:top;"><strong>${this.escapeHtml(displayValue)}</strong></td>
              </tr>`;
            })
            .join("")
        : `<tr><td style="padding:2px 0;" colspan="2">N/A</td></tr>`;

      return `
        <div style="margin-top:8px;">
          <div style="font-weight:600; margin-bottom:2px;">${this.escapeHtml(this.formatSectionTitle(title))}</div>
          <table style="border-collapse:collapse; width:100%; font-family:Monospace, sans-serif; font-size:12px; line-height:1.25; table-layout:fixed;">
            <colgroup>
              <col style="width:70%;" />
              <col style="width:30%;" />
            </colgroup>
            ${rows}
          </table>
        </div>
        <hr />
        `;
    },
    formatSectionTitle(name) {
      return name.replace(/^getEnv/, "") || name;
    },
    showDisconnectDialog() {
      const message = `
        ${this.createEnvSection("getEnvVersion", this.getEnvVersion)}
        ${this.createEnvSection("getEnvInfo", this.getEnvInfo)}
        ${this.createEnvSection("getEnvParameters", this.getEnvParameters)}
      `;

      this.$q
        .dialog({
          title: "Instance details",
          message,
          html: true,
          ok: {
            label: "Disconnect",
            color: "negative",
          },
          cancel: {
            label: "Close",
            flat: true,
          },
        })
        .onOk(() => {
          this.disconnect();
        });
    },
    disconnect() {
      if (this.$q.cookies.has("rapo_token")) {
        this.$q.cookies.remove("rapo_token");
      }
      this.removeToken();
      this.$router.push("token");
    },
  },
  computed: {
    ...mapGetters(["hideSearch", "getSearch", "getTokenIsValid", "getEnvVersion", "getEnvInfo", "getEnvParameters"]),
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
</style>
