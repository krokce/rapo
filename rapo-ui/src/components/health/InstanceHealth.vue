<template>
  <div class="instance-health" :class="{ 'instance-health-drill': drill }">
    <div v-if="error" class="text-negative">{{ error }}</div>
    <div v-else-if="!state">
      <q-skeleton v-for="row in 3" :key="row" height="96px" class="q-mb-sm" />
    </div>
    <div v-else-if="!state.enabled" class="text-grey-7">
      Instance health is switched off on this server (<span class="text-mono">[HEALTH] enabled</span> in rapo.ini).
    </div>
    <template v-else>
      <div class="row items-center text-grey-7 health-facts q-mb-sm">
        <q-btn-toggle
          v-model="hours"
          :options="spanOptions"
          dense
          no-caps
          unelevated
          size="xs"
          toggle-color="teal"
          color="grey-3"
          text-color="grey-8"
          class="health-spans q-mr-sm" />
        <span>
          Sampled every {{ state.intervals[group] }} s<template v-if="state.hours > 1">, a point per {{ stepText }}</template><template v-if="since">; since {{ since }}, when the server started</template>
        </span>
        <q-space />
        <span class="health-legend"><i class="health-legend-line" />Main</span>
        <span class="health-legend q-ml-sm"><i class="health-legend-line health-legend-second" />Second (hover a chart)</span>
        <span class="health-legend q-ml-sm"><i class="health-legend-line health-legend-threshold" />Warning level</span>
      </div>

      <div class="health-section-title ellipsis" :title="sectionLabel">{{ sectionLabel }}</div>
      <div class="health-grid">
        <health-tile v-for="tile in tiles" :key="tile.key" v-bind="tileProps(tile)" :active="Boolean(tile.drill) && drill === tile.drill" @drill="toggleDrill">
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
import { HEALTH_SPANS, diskTiles, formatUptime, healthTiles } from "../../utils/health";
import HealthSessions from "./HealthSessions.vue";
import HealthTile from "./HealthTile.vue";
import TempTablesDialog from "../TempTablesDialog.vue";

// The span shown, remembered by the browser across sessions.
const HOURS_KEY = "rapo_health_hours";

function readHours() {
  try {
    const hours = Number(localStorage.getItem(HOURS_KEY));
    return HEALTH_SPANS.includes(hours) ? hours : 1;
  } catch (error) {
    return 1;
  }
}

// The Health tabs of Instance details, one per group (os: the rapo server, db: the database), the same instance for
// both so a tab switch reloads nothing: the OS or DB metrics this server sampled in the chosen span
// (get-instance-health: the samples for 1 hour, minute aggregates beyond), then each new sample or closed minute pushed
// to the room "health" while the tab is shown. Nothing polls.
export default {
  name: "InstanceHealth",
  components: { HealthSessions, HealthTile, TempTablesDialog },
  props: {
    group: { type: String, default: "os" },
  },
  emits: ["navigate"],
  data() {
    return { state: null, error: null, drill: null, tempTables: {}, request: 0, hours: readHours() };
  },
  computed: {
    // The group's tiles, the Disk template expanded into one tile per file system.
    tiles() {
      const points = this.state[this.group] || [];
      return healthTiles(this.group).flatMap((tile) => (tile.perMount ? diskTiles(points, this.state.thresholds) : [tile]));
    },
    sectionLabel() {
      return this.group === "db" ? this.databaseLabel : this.serverLabel;
    },
    spanOptions() {
      const spans = (this.state && this.state.spans) || HEALTH_SPANS;
      return spans.map((hours) => ({ label: `${hours}h`, value: hours }));
    },
    windowMs() {
      return this.state.hours * 3600000;
    },
    // Both columns end at the latest point, so their times line up.
    end() {
      const times = [this.state.server_time, this.last("os"), this.last("db")].filter(Boolean).map((t) => new Date(t).getTime());
      return Math.max(...times);
    },
    lastDbTime() {
      return this.last("db");
    },
    stepText() {
      const minutes = Math.round(this.state.step[this.group] / 60);
      return minutes > 1 ? `${minutes} minutes` : "minute";
    },
    // When the history starts inside the span: the server started since.
    since() {
      const since = this.state.history_since;
      if (!since || new Date(since).getTime() <= this.end - this.windowMs + 60000) {
        return null;
      }
      return since.slice(0, 10) === this.state.server_time.slice(0, 10) ? since.slice(11, 16) : `${since.slice(0, 10)} ${since.slice(11, 16)}`;
    },
    serverLabel() {
      const point = this.latest("os");
      const parts = [formatUptime(point.uptime) && `up ${formatUptime(point.uptime)}`, formatUptime(point.rapo_uptime) && `rapo up ${formatUptime(point.rapo_uptime)}`].filter(Boolean);
      return `Server: ${this.state.labels.server}` + (parts.length ? ` (${parts.join(" · ")})` : "");
    },
    databaseLabel() {
      const uptime = formatUptime(this.latest("db").db_uptime);
      return `Database: ${this.state.labels.database}` + (uptime ? ` (up ${uptime})` : "");
    },
  },
  watch: {
    // Sessions and Locks are database tiles: their list closes with the tab.
    group() {
      this.drill = null;
    },
    hours(hours) {
      try {
        localStorage.setItem(HOURS_KEY, String(hours));
      } catch (error) {
        // Storage unavailable (private mode, blocked): the choice lasts for this page load only.
      }
      this.load();
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
        points: tile.points || this.state[tile.group],
        levels: this.state.levels,
        thresholds: this.state.thresholds,
        access: tile.group === "db" ? this.state.access : null,
        end: this.end,
        windowMs: this.windowMs,
        intervalMs: this.state.step[tile.group] * 1000,
      };
    },
    last(group) {
      const points = this.state && this.state[group];
      return points && points.length ? points[points.length - 1].t : null;
    },
    latest(group) {
      const points = this.state[group];
      return points.length ? points[points.length - 1] : {};
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
        const data = await api("get-instance-health", { params: { hours: this.hours }, loadingBar: false });
        if (request === this.request) {
          this.state = data;
          this.error = null;
          // A span the server does not keep (history_hours) falls back to the one it answered.
          if (data.hours !== this.hours && data.enabled) {
            this.hours = data.hours;
          }
        }
      } catch (error) {
        if (request === this.request) {
          this.error = `Failed to load the instance health: ${error.message}`;
        }
      }
    },
    // One hour shows every sample, longer spans the minutes as they close; the minute in progress the server
    // answered is replaced by its aggregate.
    onSample({ group, point, minute, levels }) {
      if (!this.state || !this.state[group]) {
        return;
      }
      this.state.levels = levels;
      const item = this.state.hours === 1 ? point : minute;
      if (!item) {
        return;
      }
      const start = new Date(item.t).getTime() - this.windowMs;
      const points = this.state[group].filter((existing) => existing.t !== item.t && new Date(existing.t).getTime() >= start);
      this.state[group] = [...points, item];
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

.health-spans .q-btn
  padding: 0 6px
  min-height: 20px
  font-size: 11px

.health-section-title
  font-size: 12px
  font-weight: 500
  color: var(--rapo-strong)
  margin-bottom: 4px

// The tiles fill the height of the tab (the parent's fixed height), each row at least $health-row high; with a session
// list open, or more tiles than fit, the rows keep that height and the tab scrolls.
$health-row: 116px

.instance-health
  display: flex
  flex-direction: column
  height: 100%

  &.instance-health-drill
    height: auto

.health-grid
  flex: 1 1 auto
  display: grid
  gap: 8px 12px
  grid-template-columns: repeat(2, minmax(0, 1fr))
  grid-auto-rows: minmax($health-row, 1fr)

.instance-health-drill .health-grid
  flex: none
  grid-auto-rows: $health-row

@media (max-width: 760px)
  .health-grid
    grid-template-columns: minmax(0, 1fr)

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

  &.health-legend-second
    border-top: 2px dashed var(--rapo-spark-2)
  &.health-legend-threshold
    border-top: 1px dashed var(--rapo-warn)

.health-link
  color: var(--rapo-info)
</style>
