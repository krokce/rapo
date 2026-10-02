<template>
  <div class="health-sessions">
    <div class="row items-center q-mb-xs">
      <div class="text-weight-bold">{{ kind === "locks" ? "Blocked sessions and their blockers" : "Database sessions" }}</div>
      <span class="text-grey-7 q-ml-sm" v-if="rows">
        {{ rows.length }}{{ truncated ? "+" : "" }} · {{ rapoCount }} of rapo
      </span>
      <q-space />
      <q-spinner v-if="loading" size="14px" color="grey-6" class="q-mr-sm" />
      <q-btn flat dense round size="sm" icon="fas fa-times" aria-label="Close" @click="$emit('close')" />
    </div>
    <div v-if="error" class="text-negative">{{ error }}</div>
    <div v-else-if="rows && !rows.length" class="text-grey-7">{{ kind === "locks" ? "No session is blocked." : "No sessions." }}</div>
    <q-virtual-scroll
      v-else-if="rows"
      type="table"
      dense
      class="list-table health-sessions-table"
      style="max-height: 240px"
      :items="rows"
      :virtual-scroll-item-size="28"
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="columns.length">
      <template #before>
        <thead>
          <tr>
            <th v-for="column in columns" :key="column.name" :class="`text-${column.align || 'left'} col-${column.name}`" :title="column.title">
              {{ column.label }}
            </th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: row }">
        <tr :key="`${row.sid},${row.serial}`" :class="{ 'health-sessions-blocked': row.blocking_session }">
          <td class="number-cell">{{ row.sid }},{{ row.serial }}</td>
          <td class="ellipsis" :title="row.username">{{ row.username }}</td>
          <td class="ellipsis" :title="row.program">
            <q-icon v-if="row.is_rapo" name="fas fa-poll" color="teal" size="11px" class="q-mr-xs" />{{ row.module || row.program }}
          </td>
          <td class="ellipsis" :title="row.action">
            <router-link v-if="row.control_id" :to="`/edit-control/${row.control_id}`" @click="$emit('navigate')">{{ row.action }}</router-link>
            <template v-else>{{ row.action }}</template>
          </td>
          <td>{{ row.status }}</td>
          <td class="ellipsis" :title="row.event">{{ row.event }}</td>
          <td class="number-cell text-right">{{ formatNumber(row.wait_seconds || 0) }}</td>
          <td class="number-cell text-right">{{ row.blocking_session || "" }}</td>
          <td class="text-mono">{{ row.sql_id }}</td>
          <td class="ellipsis" :title="row.machine">{{ row.machine }}</td>
        </tr>
      </template>
    </q-virtual-scroll>
  </div>
</template>

<script>
import { api } from "../../api";
import { formatNumber } from "../../utils/format";

const COLUMNS = [
  { name: "sid", label: "SID", title: "Session ID and serial number" },
  { name: "user", label: "User", title: "Database user of the session" },
  { name: "module", label: "Module", title: "Module the client set (rapo's sessions: rapo), else its program" },
  { name: "action", label: "Action", title: "Action the client set; for a rapo run, the control it performs" },
  { name: "status", label: "Status", title: "ACTIVE while running a call, INACTIVE while idle" },
  { name: "event", label: "Event", title: "What the session waits for, or last waited for" },
  { name: "wait", label: "Wait s", align: "right", title: "Seconds in the current wait, or since the last call of an idle session" },
  { name: "blocker", label: "Blocked by", align: "right", title: "SID of the session holding the lock this one waits for" },
  { name: "sql", label: "SQL ID", title: "SQL ID of the statement running, or last run" },
  { name: "machine", label: "Machine", title: "Client host of the session" },
];

// The sessions behind the Sessions or Locks tile, read live; refreshed when a new DB sample arrives (`stamp`).
export default {
  name: "HealthSessions",
  props: {
    kind: { type: String, required: true },
    stamp: { type: String, default: null },
  },
  emits: ["close", "navigate"],
  data() {
    return { columns: COLUMNS, rows: null, truncated: false, error: null, loading: false, request: 0 };
  },
  computed: {
    rapoCount() {
      return (this.rows || []).filter((row) => row.is_rapo).length;
    },
  },
  watch: {
    kind() {
      this.rows = null;
      this.load();
    },
    stamp() {
      this.load();
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    formatNumber,
    async load() {
      const request = ++this.request;
      this.loading = true;
      try {
        const data = await api("get-instance-sessions", { params: { kind: this.kind }, loadingBar: false });
        if (request === this.request) {
          this.rows = data.rows;
          this.truncated = data.truncated;
          this.error = null;
        }
      } catch (error) {
        if (request === this.request) {
          this.error = `Failed to read the sessions: ${error.message}`;
        }
      } finally {
        if (request === this.request) {
          this.loading = false;
        }
      }
    },
  },
};
</script>

<style lang="sass">
.health-sessions-table
  font-size: 12px

  table
    table-layout: fixed
    width: 100%
  td
    white-space: nowrap
  .col-sid
    width: 84px
  .col-user
    width: 84px
  .col-module
    width: 96px
  .col-action
    width: 112px
  .col-status
    width: 64px
  .col-wait
    width: 56px
  .col-blocker
    width: 72px
  .col-sql
    width: 116px
  .col-machine
    width: 88px

  tr.health-sessions-blocked td
    background: var(--rapo-crit-soft)
</style>
