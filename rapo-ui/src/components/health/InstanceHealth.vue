<template>
  <div class="instance-health">
    <div v-if="error" class="text-negative">{{ error }}</div>
    <div v-else-if="!state">
      <q-skeleton v-for="row in 2" :key="row" height="96px" class="q-mb-sm" />
    </div>
    <div v-else-if="!state.enabled" class="text-grey-7">
      Instance health is switched off on this server (<span class="text-mono">[HEALTH] enabled</span> in rapo.ini).
    </div>
    <template v-else>
      <div class="row items-center text-grey-7 health-facts q-mb-sm">
        <span>Last {{ state.history_minutes }} minutes of this server, sampled every {{ state.intervals.os }} s (OS) and {{ state.intervals.db }} s (database)</span>
        <q-space />
        <span class="health-legend"><i class="health-legend-line" />Host / all</span>
        <span class="health-legend q-ml-sm"><i class="health-legend-line health-legend-rapo" />Rapo</span>
        <span class="health-legend q-ml-sm"><i class="health-legend-line health-legend-threshold" />Warning level</span>
      </div>

      <div class="health-section-title">Server</div>
      <div class="health-grid health-grid-os">
        <health-tile v-for="tile in osTiles" :key="tile.key" v-bind="tileProps(tile)" />
      </div>

      <div class="health-section-title q-mt-sm">Database</div>
      <div class="health-grid health-grid-db">
        <health-tile v-for="tile in dbTiles" :key="tile.key" v-bind="tileProps(tile)" :active="drill === tile.drill" @drill="toggleDrill">
          <template v-if="tile.key === 'storage' && tempTables.total_tables" #sub="{ text }">
            {{ text }} ·
            <a href="#" class="health-link" @click.prevent.stop="$refs.tempDialog.open()">{{ tempTables.total_tables }} temporary table{{ tempTables.total_tables > 1 ? "s" : "" }}</a>
          </template>
        </health-tile>
      </div>

      <health-sessions v-if="drill" class="q-mt-sm" :kind="drill" :stamp="lastDbTime" @close="drill = null" @navigate="$emit('navigate')" />
    </template>
    <temp-tables-dialog ref="tempDialog" :tables="tempTables" @changed="loadTempTables" />
  </div>
</template>

<script>
import { api } from "../../api";
import socket from "../../socket";
import { HEALTH_TILES } from "../../utils/health";
import HealthSessions from "./HealthSessions.vue";
import HealthTile from "./HealthTile.vue";
import TempTablesDialog from "../TempTablesDialog.vue";

// The Health tab of Instance details: the OS and DB metrics this server sampled in the last hour (get-instance-health),
// then each new sample pushed to the room "health" while the tab is shown. Nothing polls.
export default {
  name: "InstanceHealth",
  components: { HealthSessions, HealthTile, TempTablesDialog },
  emits: ["navigate"],
  data() {
    return { state: null, error: null, drill: null, tempTables: {}, request: 0 };
  },
  computed: {
    osTiles() {
      return HEALTH_TILES.filter((tile) => tile.group === "os");
    },
    dbTiles() {
      return HEALTH_TILES.filter((tile) => tile.group === "db");
    },
    windowMs() {
      return this.state.history_minutes * 60000;
    },
    // Both rows end at the latest sample, so their times line up.
    end() {
      const times = [this.state.server_time, this.last("os"), this.last("db")].filter(Boolean).map((t) => new Date(t).getTime());
      return Math.max(...times);
    },
    lastDbTime() {
      return this.last("db");
    },
  },
  mounted() {
    socket.on("health:sample", this.onSample);
    socket.on("connect", this.onConnect);
    this.onConnect();
    this.loadTempTables();
  },
  unmounted() {
    socket.off("health:sample", this.onSample);
    socket.off("connect", this.onConnect);
    socket.emit("health:leave");
  },
  methods: {
    tileProps(tile) {
      return {
        tile,
        points: this.state[tile.group],
        levels: this.state.levels,
        thresholds: this.state.thresholds,
        access: tile.group === "db" ? this.state.access : null,
        end: this.end,
        windowMs: this.windowMs,
        intervalMs: this.state.intervals[tile.group] * 1000,
      };
    },
    last(group) {
      const points = this.state && this.state[group];
      return points && points.length ? points[points.length - 1].t : null;
    },
    // Joined again after a reconnect, and the history read anew since samples may have been missed.
    onConnect() {
      if (socket.connected) {
        socket.emit("health:join");
      }
      this.load();
    },
    async load() {
      const request = ++this.request;
      try {
        const data = await api("get-instance-health", { loadingBar: false });
        if (request === this.request) {
          this.state = data;
          this.error = null;
        }
      } catch (error) {
        if (request === this.request) {
          this.error = `Failed to load the instance health: ${error.message}`;
        }
      }
    },
    onSample({ group, point, levels }) {
      if (!this.state || !this.state[group]) {
        return;
      }
      const start = new Date(point.t).getTime() - this.windowMs;
      this.state[group] = [...this.state[group].filter((item) => new Date(item.t).getTime() >= start), point];
      this.state.levels = levels;
    },
    toggleDrill(kind) {
      this.drill = this.drill === kind ? null : kind;
    },
    async loadTempTables() {
      try {
        this.tempTables = await api("get-temp-tables", { loadingBar: false });
      } catch (error) {
        this.tempTables = {};
      }
    },
  },
};
</script>

<style lang="sass">
.health-facts
  font-size: 12px

.health-section-title
  font-size: 12px
  font-weight: 500
  color: var(--rapo-strong)
  margin-bottom: 4px

.health-grid
  display: grid
  gap: 8px

.health-grid-os
  grid-template-columns: repeat(4, minmax(0, 1fr))

.health-grid-db
  grid-template-columns: repeat(5, minmax(0, 1fr))

@media (max-width: 760px)
  .health-grid-os, .health-grid-db
    grid-template-columns: repeat(2, minmax(0, 1fr))

.health-legend
  display: inline-flex
  align-items: center
  font-size: 11px

.health-legend-line
  display: inline-block
  width: 14px
  height: 0
  margin-right: 4px
  border-top: 2px solid var(--rapo-spark)

  &.health-legend-rapo
    border-top: 2px dashed var(--rapo-spark-2)
  &.health-legend-threshold
    border-top: 1px dashed var(--rapo-warn)

.health-link
  color: var(--rapo-info)
</style>
