<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end" :class="activeFilters.length || sortChip ? 'q-mb-sm' : 'q-mb-lg'">
      <h2 class="row items-center text-no-wrap q-gutter-lg q-mb-none">
        <div v-if="!loaded">API tokens</div>
        <div v-else>{{ countTitle }}</div>
        <!-- The page's one primary action, on the title row as on every list page. -->
        <div>
          <q-btn unelevated color="primary" icon="fas fa-plus" label="New token" @click="$refs.editDialog.open(null)" />
        </div>
      </h2>
      <q-space />
      <div class="row q-gutter-xs q-mb-sm" v-if="loaded">
        <q-chip
          v-for="state in STATES"
          :key="state.value"
          clickable
          :class="{ 'chip-selected': filter.state === state.value }"
          @click="filter.state = filter.state === state.value ? null : state.value">
          <q-avatar :icon="state.icon" :color="state.color" text-color="white" />
          {{ state.label }} {{ stateCount(state.value) }}
        </q-chip>
      </div>
    </div>
    <filter-chips v-if="loaded" :filters="activeFilters" :sort="sortChip" class="q-mb-md" @clear="clearFilters" />

    <div class="row items-center q-mb-md">
      <div class="col text-grey-7">
        Tokens sign users in to the UI and give scripts access to the API, each up to its scopes. Only the master token of
        rapo.ini manages them.
      </div>
    </div>

    <q-banner v-if="loadError" dense rounded class="bg-red-1 text-red-10 q-mb-md">{{ loadError }}</q-banner>

    <q-virtual-scroll
      type="table"
      class="list-table token-table"
      :items="sortedTokens"
      :virtual-scroll-item-size="39"
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="8">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th v-for="column in COLUMNS" :key="column.key" :title="column.title" :class="[`text-${column.align || 'left'}`, { sortable: column.sortable }]" @click="column.sortable && toggleSort(sort, column.key)" v-keyboard="column.sortable" :aria-sort="column.sortable ? ariaSort(sort, column.key) : undefined">
              {{ column.label }}
              <q-icon v-if="column.sortable && sort.key === column.key" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left"></th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: token }">
        <tr :key="token.token_id" class="clickable-row" :class="{ 'text-grey-6': token.state !== 'active' }" v-keyboard @click="$refs.editDialog.open(token)">
          <td class="chip-cell">
            <q-chip :title="stateInfo(token.state).label">
              <q-avatar :icon="stateInfo(token.state).icon" :color="stateInfo(token.state).color" text-color="white" />
              {{ token.user_name }}
            </q-chip>
          </td>
          <td class="ellipsis">{{ token.user_email }}</td>
          <td class="ellipsis">{{ token.label }}</td>
          <td class="text-mono">{{ token.token_prefix }}…</td>
          <td class="ellipsis" :title="scopeLines(token).join('\n')">
            <span v-if="token.free_sql" class="text-weight-medium text-orange-10">SQL · </span>{{ scopeText(token) }}
          </td>
          <td>
            <span v-if="token.state === 'revoked'">Revoked {{ toDateString(token.revoked_at) }}</span>
            <span v-else-if="!token.expires_at">Never</span>
            <span v-else :class="expiryClass(token)" :title="toDateTimeString(token.expires_at)">{{ expiryText(token) }}</span>
          </td>
          <td :title="token.last_used_ip ? `From ${token.last_used_ip}` : ''">{{ token.last_used_at ? toDateTimeString(token.last_used_at) : "Never" }}</td>
          <td @click.stop>
            <q-btn aria-label="Row actions" size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, token)" />
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="!loaded">
          <skeleton-rows :rows="6" :columns="['QChip', 'text', 'text', 'text', 'text', 'text', 'text', null]" />
        </tbody>
        <tbody v-else-if="!sortedTokens.length">
          <tr>
            <td colspan="8" class="text-center text-grey-7 q-pa-lg">{{ tokens.length ? "No tokens match the filters" : "No API tokens yet" }}</td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>

    <q-menu ref="rowMenu" :target="menuTarget" no-parent-event>
      <q-list v-if="menuRow" dense class="text-no-wrap">
        <q-item clickable v-close-popup @click="$refs.editDialog.open(menuRow)">
          <q-item-section>{{ menuRow.state === "revoked" ? "View" : "Edit" }}</q-item-section>
        </q-item>
        <template v-if="menuRow.state !== 'revoked'">
          <q-item clickable>
            <q-item-section>Extend</q-item-section>
            <q-item-section side><q-icon name="fas fa-caret-right" size="12px" /></q-item-section>
            <q-menu anchor="top end" self="top start">
              <q-list dense>
                <q-item v-for="duration in DURATIONS" :key="duration.value" clickable v-close-popup @click="extend(menuRow, duration)">
                  <q-item-section>{{ duration.value === "unlimited" ? "Unlimited" : `${duration.label} from now` }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-item>
          <!-- An expired token is extended first: a new secret would not work either. -->
          <q-item v-if="menuRow.state === 'active'" clickable v-close-popup @click="confirmRegenerate(menuRow)">
            <q-item-section>Regenerate</q-item-section>
          </q-item>
          <q-separator />
          <q-item clickable v-close-popup @click="confirmRevoke(menuRow)">
            <q-item-section class="text-negative">Revoke</q-item-section>
          </q-item>
        </template>
        <q-item v-if="menuRow.state !== 'active'" clickable v-close-popup @click="confirmDelete(menuRow)">
          <q-item-section class="text-negative">Delete</q-item-section>
        </q-item>
      </q-list>
    </q-menu>

    <token-edit-dialog ref="editDialog" :areas="areas" :presets="presets" :needs-free-sql="needsFreeSql" :free-sql="freeSql" @saved="onSaved" />
    <token-reveal-dialog ref="revealDialog" />
  </q-page>
</template>

<script>
import { mapGetters } from "vuex";
import FilterChips from "./FilterChips.vue";
import SkeletonRows from "./SkeletonRows.vue";
import TokenEditDialog from "./TokenEditDialog.vue";
import TokenRevealDialog from "./TokenRevealDialog.vue";
import { api, notifyError } from "../api";
import { searchFilter, valueFilter } from "../utils/filters";
import { toDateString, toDateTimeString } from "../utils/format";
import { fillViewportToBottom } from "../utils/layout";
import { EXPIRY_WARNING_DAYS, TOKEN_DURATIONS, daysUntil, scopeSummary } from "../utils/scopes";
import { ariaSort, sortChip, sortIcon, sortRows, toggleSort } from "../utils/sort";
import persistFilters from "../mixins/persistFilters";

const STATES = [
  { value: "active", label: "Active", icon: "fas fa-check", color: "positive" },
  { value: "expired", label: "Expired", icon: "fas fa-hourglass-end", color: "orange-8" },
  { value: "revoked", label: "Revoked", icon: "fas fa-ban", color: "grey-6" },
];

const COLUMNS = [
  { key: "user_name", label: "User", title: "The person the token belongs to, and whether the token is active, expired or revoked; click a row to edit it (a revoked one opens read only)", sortable: true },
  { key: "user_email", label: "Email", title: "The user's email address; what the database records as the user of the changes made with the token", sortable: true },
  { key: "label", label: "Label", title: "What the token is for, e.g. UI or the name of a script", sortable: true },
  { key: "token_prefix", label: "Token", title: "The first characters of the token, to tell it apart; the whole token is shown only when it is created or regenerated" },
  { key: "scopes", label: "Scopes", title: "The areas the token reaches and their level; SQL: it may send SQL text (Free SQL)" },
  { key: "expires_at", label: "Expires", title: "When the token stops working", sortable: true },
  { key: "last_used_at", label: "Last used", title: "When the token was last used (written at most once a minute), and from which address", sortable: true },
];

const DEFAULT_SORT = { key: null, dir: "asc" };
const SORT_LABELS = { user_name: "User", user_email: "Email", label: "Label", expires_at: "Expires", last_used_at: "Last used" };

export default {
  name: "TokensPage",
  mixins: [persistFilters("tokens", ["filter", "sort"])],
  components: { FilterChips, SkeletonRows, TokenEditDialog, TokenRevealDialog },
  data() {
    return {
      STATES,
      COLUMNS,
      DURATIONS: TOKEN_DURATIONS,
      loaded: false,
      loadError: null,
      tokens: [],
      areas: [],
      presets: {},
      needsFreeSql: {},
      freeSql: { title: "Free SQL", description: "" },
      filter: { state: null },
      sort: { ...DEFAULT_SORT },
      menuTarget: false,
      menuTokenId: null,
    };
  },
  methods: {
    sortIcon,
    ariaSort,
    toggleSort,
    toDateString,
    toDateTimeString,
    fillViewportToBottom,
    async load() {
      try {
        const data = await api("get-api-tokens");
        this.tokens = data.tokens;
        this.areas = data.areas;
        this.presets = data.presets;
        this.needsFreeSql = data.needs_free_sql;
        this.freeSql = data.free_sql;
        this.loadError = null;
      } catch (error) {
        this.loadError = error.message;
      }
      this.loaded = true;
    },
    stateInfo(state) {
      return STATES.find((item) => item.value === state) || STATES[0];
    },
    stateCount(state) {
      return this.tokens.filter((token) => token.state === state).length;
    },
    scopeLines(token) {
      return scopeSummary(token.scopes, this.areas);
    },
    scopeText(token) {
      const lines = this.scopeLines(token);
      return lines.length ? lines.join(" · ") : "No area";
    },
    expiryText(token) {
      const days = daysUntil(token.expires_at);
      if (token.state === "expired") {
        return `Expired ${toDateString(token.expires_at)}`;
      }
      return days < 1 ? "Today" : `In ${days} day${days === 1 ? "" : "s"}`;
    },
    expiryClass(token) {
      if (token.state === "expired") {
        return "text-orange-10";
      }
      return daysUntil(token.expires_at) <= EXPIRY_WARNING_DAYS ? "text-orange-10 text-weight-medium" : "";
    },
    openRowMenu(event, row) {
      this.menuTarget = event.currentTarget;
      this.menuTokenId = row.token_id;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
    clearFilters() {
      this.filter.state = null;
      this.$store.commit("updateSearch", "");
    },
    onSaved(result) {
      if (result.token) {
        this.$refs.revealDialog.open(result);
      } else {
        this.$q.notify({ type: "positive", message: `Token of ${result.user_name} was saved.` });
      }
      this.load();
    },
    async extend(token, duration) {
      try {
        const row = await api("extend-api-token", { method: "POST", params: { id: token.token_id, duration: duration.value } });
        this.$q.notify({ type: "positive", message: `Token of ${token.user_name} now expires ${row.expires_at ? toDateTimeString(row.expires_at) : "never"}.` });
        await this.load();
      } catch (error) {
        notifyError("Token was not extended.", error);
      }
    },
    confirmRegenerate(token) {
      this.$q
        .dialog({
          title: "Regenerate token",
          message: `${token.user_name} (${token.label || token.user_email}) gets a new token; the current one (${token.token_prefix}…) stops working at once. Scopes and expiry stay.`,
          cancel: true,
          persistent: true,
          ok: { label: "Regenerate", color: "primary" },
        })
        .onOk(async () => {
          try {
            this.$refs.revealDialog.open(await api("regenerate-api-token", { method: "POST", params: { id: token.token_id } }));
            await this.load();
          } catch (error) {
            notifyError("Token was not regenerated.", error);
          }
        });
    },
    confirmRevoke(token) {
      this.$q
        .dialog({
          title: "Revoke token",
          message: `The token of ${token.user_name} (${token.token_prefix}…) stops working at once; signed-in pages are signed out. It stays listed.`,
          cancel: true,
          persistent: true,
          ok: { label: "Revoke", color: "negative" },
        })
        .onOk(async () => {
          try {
            await api("revoke-api-token", { method: "POST", params: { id: token.token_id } });
            this.$q.notify({ type: "positive", message: `Token of ${token.user_name} was revoked.` });
            await this.load();
          } catch (error) {
            notifyError("Token was not revoked.", error);
          }
        });
    },
    confirmDelete(token) {
      this.$q
        .dialog({ title: "Delete token", message: `Delete the ${token.state} token of ${token.user_name} (${token.token_prefix}…)?`, cancel: true, persistent: true, ok: { label: "Delete", color: "negative" } })
        .onOk(async () => {
          try {
            await api("delete-api-token", { method: "DELETE", params: { id: token.token_id } });
            await this.load();
          } catch (error) {
            notifyError("Token was not deleted.", error);
          }
        });
    },
  },
  computed: {
    ...mapGetters(["getSearch"]),
    countTitle() {
      const total = this.tokens.length;
      const shown = this.filteredTokens.length;
      const count = this.activeFilters.length ? `${shown} of ${total}` : String(shown);
      return `${count} API token${(this.activeFilters.length ? total : shown) === 1 ? "" : "s"}`;
    },
    sortChip() {
      return sortChip(this.sort, DEFAULT_SORT, SORT_LABELS, "latest first");
    },
    activeFilters() {
      const filter = this.filter;
      return [
        ...valueFilter("state", "State", filter.state, () => (filter.state = null), { label: filter.state ? this.stateInfo(filter.state).label : null }),
        ...searchFilter(this.$store),
      ];
    },
    menuRow() {
      return this.tokens.find((item) => item.token_id === this.menuTokenId) || null;
    },
    filteredTokens() {
      const search = (this.getSearch || "").toUpperCase();
      return this.tokens.filter((token) => {
        const text = `${token.user_name} ${token.user_email} ${token.label || ""} ${token.token_prefix}`.toUpperCase();
        return (!search || text.includes(search)) && (!this.filter.state || token.state === this.filter.state);
      });
    },
    sortedTokens() {
      if (!this.sort.key) {
        return this.filteredTokens;
      }
      return sortRows(this.filteredTokens, (item) => item[this.sort.key], this.sort.dir);
    },
  },
  mounted() {
    this.load();
  },
};
</script>

<style scoped>
.token-table :deep(table) {
  table-layout: fixed;
  min-width: 1000px;
}
.token-table th:nth-child(1) { width: 200px; }
.token-table th:nth-child(2) { width: 220px; }
.token-table th:nth-child(3) { width: 140px; }
.token-table th:nth-child(4) { width: 130px; }
.token-table th:nth-child(6) { width: 140px; }
.token-table th:nth-child(7) { width: 160px; }
.token-table th:nth-child(8) { width: 62px; }
</style>
