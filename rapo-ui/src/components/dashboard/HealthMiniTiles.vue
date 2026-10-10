<template>
  <div class="mini-health__root" :style="{ '--columns': columns }">
    <q-resize-observer @resize="onResize" />
    <div v-if="error" class="text-negative text-caption">{{ error }}</div>
    <div v-else-if="!state" class="mini-health">
      <q-skeleton v-for="index in 12" :key="index" height="100%" />
    </div>
    <div v-else-if="!state.enabled" class="text-grey-7 text-caption">
      Instance health is switched off on this server (<span class="text-mono">[HEALTH] enabled</span> in rapo.ini).
    </div>
    <template v-else>
      <div v-for="group in groups" :key="group.key" class="mini-health__group">
        <div class="mini-health__title dash-text ellipsis" :title="group.label"><q-icon :name="group.icon" size="11px" class="q-mr-xs" />{{ group.label }}</div>
        <div class="mini-health">
          <div
            v-for="tile in group.tiles"
            :key="tile.key"
            class="mini-health__tile"
            :class="tile.level ? `mini-health__tile--${tile.level}` : ''"
            :title="tile.text"
            v-keyboard:button
            @click="$emit('open', group.key)">
            <div class="row no-wrap items-baseline">
              <div class="mini-health__name dash-label ellipsis">{{ tile.title }}</div>
              <q-space />
              <div class="mini-health__value dash-value">{{ tile.value }}</div>
            </div>
            <health-sparkline
              v-if="!tile.denied"
              class="mini-health__chart"
              :points="tile.points"
              :series="tile.series"
              :end="end"
              :window-ms="windowMs"
              :interval-ms="state.step[tile.group] * 1000"
              :max="tile.max || null"
              :threshold="tile.threshold"
              :level="tile.level"
              :format="tile.format" />
            <div v-else class="mini-health__denied dash-note">No access</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { api } from "../../api";
import socket, { joinHealthRoom, leaveHealthRoom } from "../../socket";
import { gridColumns } from "../../utils/dashboard";
import { diskTiles, healthTiles, missingGrants, tileLevel } from "../../utils/health";
import HealthSparkline from "../health/HealthSparkline.vue";

// The instance health in two rows of small tiles, the rapo server's and the database's: each metric's value now, its
// level, and a line over the span (24 hours, or 7 days for 7d and 30d, from the stored minutes); the closed minutes
// pushed to the room "health" are added while the page is shown. A click opens Instance details on that group. Each group
// is a row of 6 (two of 3, three of 2 as the width shrinks): the file systems are one Disk tile here, the fullest.
export default {
  name: "HealthMiniTiles",
  components: { HealthSparkline },
  props: {
    // The Dashboard's span: 24h, else the 7 days kept.
    span: { type: String, default: "24h" },
    // Whether the page is shown (kept alive): the room is left while it is not.
    active: { type: Boolean, default: true },
  },
  emits: ["open"],
  data() {
    // historyMs: how far back the server's history goes, as last answered; width: the panel's, for the columns.
    return { state: null, error: null, joined: false, request: 0, historyMs: null, width: 0 };
  },
  computed: {
    columns() {
      const count = this.state && this.state.enabled ? Math.max(...this.groups.map((group) => group.tiles.length)) : 6;
      return gridColumns(this.width, count, { min: 140, choices: [6, 3, 2, 1] });
    },
    // 24 hours for 24h, else the 7 days kept; the last hour's samples while the history is shorter than that (a new
    // installation), since a longer span would merge it into a point or two.
    hours() {
      if (this.historyMs !== null && this.historyMs < 3600000) {
        return 1;
      }
      const spans = (this.state && this.state.spans) || [];
      return this.span !== "24h" && spans.includes(168) ? 168 : 24;
    },
    // The span, or less while the points shown start later (a new installation, a restart), so that the lines fill
    // the tiles.
    windowMs() {
      const span = this.state.hours * 3600000;
      const firsts = ["os", "db"].map((group) => this.state[group] && this.state[group][0]).filter(Boolean);
      if (!firsts.length) {
        return span;
      }
      const first = Math.min(...firsts.map((point) => new Date(point.t).getTime()));
      return Math.min(span, Math.max(this.end - first, 600000));
    },
    end() {
      const times = [this.state.server_time, ...["os", "db"].map((group) => this.last(group))].filter(Boolean).map((time) => new Date(time).getTime());
      return Math.max(...times);
    },
    groups() {
      return [
        { key: "os", icon: "fas fa-server", label: `Server ${this.state.labels.server}`, tiles: this.tilesOf("os") },
        { key: "db", icon: "fas fa-database", label: `Database ${this.state.labels.database}`, tiles: this.tilesOf("db") },
      ];
    },
  },
  watch: {
    active: {
      immediate: true,
      handler(active) {
        if (active) {
          this.start();
        } else {
          this.stop();
        }
      },
    },
    hours() {
      this.load();
    },
  },
  unmounted() {
    this.stop();
  },
  methods: {
    onResize({ width }) {
      this.width = width;
    },
    start() {
      if (this.joined) {
        return;
      }
      this.joined = true;
      socket.on("health:sample", this.onSample);
      socket.on("connect", this.load);
      joinHealthRoom();
      this.load();
    },
    stop() {
      if (!this.joined) {
        return;
      }
      this.joined = false;
      socket.off("health:sample", this.onSample);
      socket.off("connect", this.load);
      leaveHealthRoom();
    },
    async load() {
      const request = ++this.request;
      try {
        const state = await api("get-instance-health", { params: { hours: this.hours }, loadingBar: false });
        if (request === this.request) {
          this.state = state;
          this.error = null;
          const since = state.history_since ? new Date(state.history_since).getTime() : null;
          this.historyMs = since ? new Date(state.server_time).getTime() - since : null;
        }
      } catch (error) {
        if (request === this.request) {
          this.error = `Failed to load the instance health: ${error.message}`;
        }
      }
    },
    // A sample (the 1 hour span) or a closed minute joins the line; the levels follow every sample.
    onSample({ group, point, minute, levels }) {
      if (!this.state || !this.state[group]) {
        return;
      }
      this.state.levels = levels;
      const item = this.state.hours === 1 ? point : minute;
      if (!item) {
        return;
      }
      const start = new Date(item.t).getTime() - this.state.hours * 3600000;
      this.state[group] = [...this.state[group].filter((existing) => existing.t !== item.t && new Date(existing.t).getTime() >= start), item];
    },
    // The file system of the worst level, else the fullest, as the one Disk tile; its tooltip lists them all.
    fullestDisk(tiles) {
      if (!tiles.length) {
        return [];
      }
      const rank = { crit: 2, warn: 1 };
      const used = (tile) => {
        const point = [...tile.points].reverse().find((item) => item.used_percent !== null && item.used_percent !== undefined);
        return point ? point.used_percent : -1;
      };
      const [fullest] = [...tiles].sort((a, b) => (rank[b.level] || 0) - (rank[a.level] || 0) || used(b) - used(a));
      const mounts = tiles.map((tile) => `${tile.title.replace(/^Disk /, "")} ${used(tile) < 0 ? "–" : tile.format(used(tile))}`).join(" · ");
      return [{ ...fullest, hint: tiles.length > 1 ? `${fullest.hint}\nAll: ${mounts}` : fullest.hint }];
    },
    last(group) {
      const points = this.state && this.state[group];
      return points && points.length ? points[points.length - 1].t : null;
    },
    tilesOf(group) {
      const points = this.state[group] || [];
      return healthTiles(group)
        .flatMap((tile) => (tile.perMount ? this.fullestDisk(diskTiles(points, this.state.thresholds)) : [tile]))
        .map((tile) => {
          const own = tile.points || points;
          const latest = [...own].reverse().find((point) => point[tile.series[0].field] !== null && point[tile.series[0].field] !== undefined);
          const rule = !tile.noThreshold && tile.rules[0];
          const limits = rule && this.state.thresholds[rule];
          const denied = missingGrants(tile, tile.group === "db" ? this.state.access : null).length > 0;
          return {
            ...tile,
            points: own,
            denied,
            value: denied ? "" : tile.format(latest ? latest[tile.series[0].field] : null),
            text: latest ? `${tile.hint}\n${tile.sub(latest)}` : tile.hint,
            level: "level" in tile ? tile.level : tileLevel(tile, this.state.levels),
            threshold: limits && limits[0] !== null ? limits[0] : null,
          };
        });
    },
  },
};
</script>

<style scoped>
.mini-health__root {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mini-health__group {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.mini-health__title {
  font-weight: 500;
  margin-bottom: 3px;
}

.mini-health {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(var(--columns), minmax(0, 1fr));
  grid-auto-rows: minmax(64px, 1fr);
}

.mini-health__tile {
  display: flex;
  flex-direction: column;
  padding: 6px 10px 0;
  border: 1px solid var(--rapo-panel-border);
  border-left: 3px solid var(--rapo-spark);
  border-radius: 6px;
  background: var(--rapo-surface);
  cursor: pointer;
  min-width: 0;
  overflow: hidden;
}

.mini-health__tile:hover {
  background: var(--rapo-surface-alt);
}

.mini-health__tile--warn {
  border-left-color: var(--rapo-warn);
}

.mini-health__tile--warn .mini-health__value {
  color: var(--rapo-warn);
}

.mini-health__tile--crit {
  border-left-color: var(--rapo-crit);
}

.mini-health__tile--crit .mini-health__value {
  color: var(--rapo-crit);
}

.mini-health__value {
  white-space: nowrap;
  margin-left: 6px;
}

/* The line takes what the tile leaves, edge to edge. */
.mini-health__chart {
  flex: 1 1 auto;
  min-height: 28px;
  margin: 2px -10px 0;
}

.mini-health__denied {
  flex: 1 1 auto;
}
</style>
