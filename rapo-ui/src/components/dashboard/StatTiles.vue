<template>
  <div class="stat-tiles" :style="{ '--columns': columns }">
    <q-resize-observer @resize="onResize" />
    <div
      v-for="tile in shown"
      :key="tile.key"
      class="stat-tile column no-wrap"
      :class="[`stat-tile--${tile.topic}`, tile.state ? `stat-tile--${tile.state}` : '']"
      :title="tile.hint"
      v-keyboard:button
      @click="$emit('open', tile)">
      <div class="row no-wrap">
        <div class="col column no-wrap stat-tile__text">
          <div class="stat-tile__title dash-label ellipsis">{{ tile.title }}</div>
          <div class="stat-tile__value dash-value ellipsis" :title="tile.exact">
            <q-icon v-if="tile.icon" :name="tile.icon" size="14px" class="q-mr-xs stat-tile__dot" :style="{ color: tile.dotColor }" />{{ tile.value }}
          </div>
          <div class="stat-tile__sub dash-note ellipsis" :class="tile.deltaClass" :title="tile.sub">{{ tile.sub }}</div>
        </div>
        <svg v-if="tile.ring" class="stat-tile__ring" viewBox="0 0 40 40" aria-hidden="true">
          <circle v-for="(segment, index) in tile.ring.segments" :key="index" cx="20" cy="20" r="16" :class="segment.on ? 'stat-tile__ring--on' : 'stat-tile__ring--off'" :stroke-dasharray="segment.dash" :stroke-dashoffset="segment.offset" />
          <text x="20" y="20" class="stat-tile__ring-text">{{ tile.ring.text }}</text>
        </svg>
      </div>
      <svg v-if="tile.spark" class="stat-tile__spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true">
        <polygon :points="tile.spark.area" />
        <polyline :points="tile.spark.line" />
      </svg>
      <div v-else class="stat-tile__spark" />
    </div>
  </div>
</template>

<script>
import { schedulerState } from "../../constants";
import { compactNumber, formatNumber } from "../../utils/format";
import { LEVEL_TEXT } from "../../utils/health";
import { gridColumns, tileDelta } from "../../utils/dashboard";
import { paletteColor } from "../../utils/palette";

// What each tile counts: its key in the tiles part, how its value reads, when it is bad, and the page it opens.
const COUNTS = [
  { key: "runs", title: "Runs", hint: "Runs started today (app server clock)", link: { path: "/results" } },
  { key: "run_errors", title: "Run errors", hint: "Runs started today that ended in error", bad: true, errors: true, link: { path: "/results", query: { status: "E" } } },
  { key: "run_warnings", title: "Run warnings", hint: "Runs today that ended with a warning (non-unique keys, limits reached)", bad: true, warn: true, link: { path: "/results", query: { warnings: "1" } } },
  { key: "files_success", title: "Files success", hint: "Files of today loaded successfully (SUCCESS, database clock)", files: true, link: { path: "/files", query: { status: "SUCCESS" } } },
  { key: "records_loaded", title: "Records loaded", hint: "Records written by the files of today", files: true, compact: true, link: { path: "/files" } },
  { key: "records_rejected", title: "Rejected", hint: "Records rejected by the files of today", files: true, compact: true, bad: true, warn: true, rejected: true, link: { path: "/files" } },
  { key: "files_error", title: "Files in error", hint: "Files of today that ended in ERROR", files: true, bad: true, alert: true, link: { path: "/files", query: { status: "ERROR" } } },
  { key: "files_waiting", title: "Files in input", hint: "Files waiting in the input directories of the active datasources, as last scanned", files: true, compact: true, waiting: true, link: { path: "/files" } },
  {
    key: "files_processing",
    title: "Files in processing",
    hint: "Files of any day in the PDI Core file log loading (Started, Processing) or waiting to be loaded (Waiting)",
    files: true,
    compact: true,
    processing: true,
    link: { path: "/files", query: { status: "WAITING,STARTED,PROCESSING" } },
  },
  { key: "kpi_alarms", title: "KPI alarms", hint: "KPI values of today's runs at alarm level 2 or 3", kpi: true, bad: true, warn: true, section: "kpis" },
];

// The order of the tiles, two rows of 6 when all are there, by topic: the runs and what goes wrong with them, then the
// instance; the files along their way (waiting in the input, loading), then what came of them in pairs (files loaded
// and in error, records loaded and rejected).
const ORDER = ["runs", "run_errors", "run_warnings", "kpi_alarms", "scheduler", "health", "files_waiting", "files_processing", "files_success", "files_error", "records_loaded", "records_rejected"];

// "45 s", "12 min", "3 h", "2 d".
function age(seconds) {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h`;
  return `${Math.round(seconds / 86400)} d`;
}

// The day in numbers, a tile each: today's value, how it compares with the same weekday a week ago up to the same time
// of day, the 7 days to today as a line; the scheduler's state and the instance health among them. Rows of 6 (4, 3, 2 as
// the width shrinks), so 12 tiles fill two. A click opens its page.
export default {
  name: "StatTiles",
  props: {
    // The tiles part of get-dashboard (null while loading).
    tiles: { type: Object, default: null },
    scheduler: { type: Object, default: null },
    health: { type: Object, default: null },
  },
  emits: ["open"],
  data() {
    return { width: 0 };
  },
  computed: {
    shown() {
      const tiles = COUNTS.filter((count) => this.tiles && this.tiles[count.key]).map((count) => this.countTile(count));
      tiles.push(this.schedulerTile, this.healthTile);
      return tiles.filter(Boolean).sort((a, b) => ORDER.indexOf(a.key) - ORDER.indexOf(b.key));
    },
    columns() {
      return gridColumns(this.width, this.shown.length);
    },
    schedulerTile() {
      const status = this.scheduler;
      const state = schedulerState(status && status.state);
      const runner = (status && status.runner) || {};
      const running = (runner.running || []).length;
      const queued = (runner.queued || []).length;
      return {
        key: "scheduler",
        topic: "instance",
        title: "Scheduler",
        value: state.label,
        icon: "fas fa-circle",
        dotColor: paletteColor(state.color),
        sub: status ? `${queued} queued` : "",
        hint: `${state.description}\n${running} of ${runner.capacity || 0} slots of this server running, ${queued} queued`,
        ring: status ? this.ring(running, runner.capacity || 0) : null,
        state: status && (status.disabled || status.state === "off") ? "alert" : null,
        link: { path: "/scheduler" },
      };
    },
    healthTile() {
      const health = this.health;
      if (!health || !health.enabled) {
        return null;
      }
      const level = health.level;
      return {
        key: "health",
        topic: "instance",
        title: "Health",
        hint: "The worst level of the instance health metrics; opens Instance details",
        value: level ? LEVEL_TEXT[level] : "OK",
        icon: "fas fa-heartbeat",
        dotColor: level ? `var(--rapo-${level})` : paletteColor("teal"),
        sub: level ? "A metric reached its level" : "All metrics within their levels",
        state: level === "crit" ? "alert" : level === "warn" ? "warn" : null,
        action: "health",
      };
    },
  },
  methods: {
    onResize({ width }) {
      this.width = width;
    },
    countTile(count) {
      const tile = this.tiles[count.key];
      const value = tile.today;
      const delta = tileDelta(tile, count.bad);
      let text = "–";
      if (value !== null && value !== undefined) {
        text = count.compact ? compactNumber(value) : formatNumber(value);
      }
      let state = null;
      if (count.alert && value > 0) {
        state = "alert";
      } else if (count.warn && value > 0) {
        state = "warn";
      }
      let sub = delta ? delta.text : "No comparison";
      // Whether the note is the comparison, colored by it.
      let compared = true;
      let link = count.link;
      if (count.waiting) {
        // The files waiting: how long the oldest waits and the datasources stalled, the comparison on hover.
        sub = value === null || value === undefined ? "Not scanned recently" : tile.oldest_age ? `oldest ${age(tile.oldest_age)}` : "none waiting";
        if (tile.stalled) {
          state = "alert";
          sub = `${tile.stalled} stalled · ${sub}`;
          link = { path: "/datasources", query: { issue: "stalled" } };
        }
      }
      let hint = count.waiting && delta ? `${count.hint} (${delta.text})` : count.hint;
      if (count.errors) {
        // The runs in error, and the controls still failing (their latest run in error): red while any is, orange when
        // every one recovered.
        const failing = (this.tiles.failing_controls && this.tiles.failing_controls.today) || 0;
        if (failing || value) {
          compared = false;
        }
        if (failing) {
          state = "alert";
          sub = `${formatNumber(failing)} control${failing === 1 ? "" : "s"} still failing`;
        } else if (value) {
          state = "warn";
          sub = "all recovered";
        }
        hint = delta ? `${hint} (${delta.text})` : hint;
      }
      if (count.rejected && value) {
        sub = `${tile.rate !== null && tile.rate !== undefined ? `${formatNumber(tile.rate, tile.rate < 10 ? 2 : 1)}% of read` : ""}${delta && delta.up !== null ? ` · ${delta.text.replace(" vs last week", "")}` : ""}`;
        hint = delta ? `${hint} (${delta.text})` : hint;
      }
      if (count.processing) {
        // Now only: what loads and what waits, the oldest's age on hover.
        sub = value === null || value === undefined ? "Not available" : `${formatNumber(tile.loading || 0)} loading · ${formatNumber(tile.waiting || 0)} waiting`;
        if (tile.oldest_age) {
          hint = `${hint}; the oldest started ${age(tile.oldest_age)} ago`;
        }
      }
      return {
        ...count,
        topic: count.files ? "files" : "runs",
        link,
        state,
        value: text,
        exact: value !== null && value !== undefined ? formatNumber(value) : "",
        hint,
        sub,
        deltaClass: compared && delta && delta.up !== null ? (delta.bad ? "stat-tile__sub--bad" : "stat-tile__sub--good") : "",
        spark: this.spark(tile.days),
      };
    },
    // A ring of the slots, one segment each (a gap between them), the running ones first: stroke dashes on a circle of
    // radius 16 starting at the top.
    ring(running, capacity) {
      const length = 2 * Math.PI * 16;
      const count = Math.max(capacity, 1);
      const gap = count > 1 ? 2 : 0;
      const part = length / count;
      const segments = Array.from({ length: count }, (_, index) => ({
        on: index < running,
        dash: `${Math.max(part - gap, 0.5).toFixed(2)} ${(length - Math.max(part - gap, 0.5)).toFixed(2)}`,
        offset: (length / 4 - index * part).toFixed(2),
      }));
      return { segments, text: `${running}/${capacity}` };
    },
    // The 7 days over 100 x 30 as a line and the area under it (unknown days left out).
    spark(days) {
      const values = (days || []).map((value) => (value === null || value === undefined ? null : Number(value)));
      const known = values.filter((value) => value !== null);
      if (known.length < 2) {
        return null;
      }
      const max = Math.max(...known);
      const min = Math.min(...known, 0);
      const range = max - min || 1;
      const points = values
        .map((value, index) => (value === null ? null : [(index * 100) / (values.length - 1), 28 - ((value - min) * 26) / range]))
        .filter(Boolean);
      const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
      return { line, area: `${points[0][0].toFixed(1)},30 ${line} ${points[points.length - 1][0].toFixed(1)},30` };
    },
  },
};
</script>

<style scoped>
.stat-tiles {
  position: relative;
  display: grid;
  grid-template-columns: repeat(var(--columns), minmax(0, 1fr));
  grid-auto-rows: minmax(76px, 1fr);
  gap: 8px;
}

.stat-tile {
  --tile-color: var(--rapo-spark);
  padding: 8px 12px 0;
  border: 1px solid var(--rapo-panel-border);
  border-left: 3px solid var(--tile-color);
  border-radius: 6px;
  background: var(--rapo-surface);
  cursor: pointer;
  min-width: 0;
  overflow: hidden;
  container-type: inline-size;
}

.stat-tile:hover {
  background: var(--rapo-surface-alt);
}

/* The topic of a tile tints its edge and its week: the runs, the instance, the files. */
.stat-tile--runs {
  --tile-color: var(--rapo-spark-2);
}

.stat-tile--instance {
  --tile-color: var(--rapo-label);
}

.stat-tile--files {
  --tile-color: var(--rapo-spark);
}

.stat-tile--alert {
  --tile-color: var(--rapo-crit);
}

.stat-tile--alert .stat-tile__value {
  color: var(--rapo-crit);
}

.stat-tile--warn {
  --tile-color: var(--rapo-warn);
}

.stat-tile--warn .stat-tile__value {
  color: var(--rapo-warn);
}

.stat-tile__value {
  margin-top: 2px;
}

.stat-tile__text {
  min-width: 0;
}

/* The slots of the scheduler: running in the instance's color, free grey. */
.stat-tile__ring {
  flex: 0 0 60px;
  width: 60px;
  height: 60px;
  margin: 4px 0 0 8px;
}

/* A narrow tile keeps its value whole: a smaller ring. */
@container (max-width: 240px) {
  .stat-tile__ring {
    flex-basis: 44px;
    width: 44px;
    height: 44px;
    margin-left: 4px;
  }
}

.stat-tile__ring circle {
  fill: none;
  stroke-width: 6;
}

.stat-tile__ring--on {
  stroke: var(--rapo-spark);
}

.stat-tile__ring--off {
  stroke: var(--rapo-grid);
}

.stat-tile__ring-text {
  font-size: 10px;
  font-weight: 600;
  fill: var(--rapo-header-text);
  text-anchor: middle;
  dominant-baseline: central;
}

.stat-tile__dot {
  vertical-align: 3px;
}

/* The week under the numbers, edge to edge of the tile. */
.stat-tile__spark {
  flex: 1 1 0;
  min-height: 0;
  width: calc(100% + 24px);
  margin: 2px -12px 0;
  display: block;
}

.stat-tile__spark polygon {
  fill: var(--tile-color);
  opacity: 0.14;
}

.stat-tile__spark polyline {
  fill: none;
  stroke: var(--tile-color);
  stroke-width: 1.5;
  vector-effect: non-scaling-stroke;
}

.stat-tile__sub--bad {
  color: var(--rapo-crit);
}

.stat-tile__sub--good {
  color: var(--rapo-teal);
}
</style>
