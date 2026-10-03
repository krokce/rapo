<template>
  <div class="health-tile" :class="[level ? `health-tile-${level}` : '', { 'health-tile-clickable': clickable, 'health-tile-active': active }]" @click="clickable && $emit('drill', tile.drill)">
    <div class="row items-baseline no-wrap">
      <div class="health-tile-title ellipsis" :title="tile.hint">{{ tile.title }}</div>
      <q-space />
      <q-icon v-if="tile.drill && !grants.length" :name="active ? 'fas fa-chevron-up' : 'fas fa-list'" size="9px" class="health-tile-drill q-mr-xs" />
      <div class="health-tile-value" :title="level ? levelText : ''">{{ grants.length ? "" : tile.format(value) }}</div>
    </div>
    <template v-if="grants.length">
      <div class="health-tile-empty">
        No access
        <q-tooltip>This database user may not read {{ grants.join(", ") }}. A DBA can grant it: {{ grants.map((grant) => `GRANT SELECT ON ${grant} TO <user>`).join("; ") }}</q-tooltip>
      </div>
    </template>
    <template v-else-if="last">
      <health-sparkline
        class="health-tile-chart"
        :points="points"
        :series="tile.series"
        :end="end"
        :window-ms="windowMs"
        :interval-ms="intervalMs"
        :max="tile.max || null"
        :threshold="threshold"
        :level="level"
        :format="tile.format" />
      <div class="health-tile-sub ellipsis" :title="sub">
        <slot name="sub" :text="sub">{{ sub }}</slot>
      </div>
    </template>
    <div v-else class="health-tile-empty">{{ error || "Waiting for the first sample..." }}</div>
  </div>
</template>

<script>
import HealthSparkline from "./HealthSparkline.vue";
import { LEVEL_TEXT, missingGrants, tileLevel } from "../../utils/health";

// One metric of the instance health: its current value, the span as a chart filling the tile's height, and a line of
// details.
export default {
  name: "HealthTile",
  components: { HealthSparkline },
  props: {
    tile: { type: Object, required: true },
    points: { type: Array, required: true },
    levels: { type: Object, default: () => ({}) },
    thresholds: { type: Object, default: () => ({}) },
    access: { type: Object, default: null },
    end: { type: Number, required: true },
    windowMs: { type: Number, required: true },
    intervalMs: { type: Number, required: true },
    active: { type: Boolean, default: false },
  },
  emits: ["drill"],
  computed: {
    grants() {
      return missingGrants(this.tile, this.access);
    },
    last() {
      for (let index = this.points.length - 1; index >= 0; index -= 1) {
        const value = this.points[index][this.tile.series[0].field];
        if (value !== null && value !== undefined) {
          return this.points[index];
        }
      }
      return null;
    },
    value() {
      return this.last ? this.last[this.tile.series[0].field] : null;
    },
    sub() {
      return this.last ? this.tile.sub(this.last) : "";
    },
    // Why the latest sample has no value, e.g. a query that failed.
    error() {
      const point = this.points[this.points.length - 1];
      const errors = (point && point.errors) || {};
      const messages = Object.values(errors);
      return messages.length ? messages[0] : null;
    },
    // A disk tile brings its own level (utils/health.js diskTiles).
    level() {
      return "level" in this.tile ? this.tile.level : tileLevel(this.tile, this.levels);
    },
    levelText() {
      return LEVEL_TEXT[this.level];
    },
    threshold() {
      const rule = !this.tile.noThreshold && this.tile.rules[0];
      const values = rule && this.thresholds[rule];
      return values && values[0] !== null ? values[0] : null;
    },
    clickable() {
      return Boolean(this.tile.drill) && !this.grants.length;
    },
  },
};
</script>

<style lang="sass">
.health-tile
  padding: 6px 8px 4px
  border: 1px solid var(--rapo-panel-border)
  border-left: 3px solid var(--rapo-spark)
  border-radius: 4px
  background: var(--rapo-surface)
  min-width: 0
  min-height: 0
  display: flex
  flex-direction: column

  &.health-tile-warn
    border-left-color: var(--rapo-warn)
    .health-tile-value
      color: var(--rapo-warn)
  &.health-tile-crit
    border-left-color: var(--rapo-crit)
    .health-tile-value
      color: var(--rapo-crit)

  &.health-tile-clickable
    cursor: pointer
    &:hover
      background: var(--rapo-surface-alt)
  &.health-tile-active
    background: var(--rapo-surface-alt)

.health-tile-title
  font-size: 11px
  font-weight: 500
  text-transform: uppercase
  letter-spacing: 0.04em
  color: var(--rapo-label)

.health-tile-drill
  color: var(--rapo-label)

.health-tile-value
  font-size: 17px
  font-weight: 500
  line-height: 1.2
  color: var(--rapo-header-text)
  white-space: nowrap

.health-tile-chart
  flex: 1 1 auto
  margin-top: 2px

.health-tile-sub
  font-size: 11px
  line-height: 1.6
  color: var(--rapo-muted)

.health-tile-empty
  flex: 1 1 auto
  min-height: 58px
  display: flex
  align-items: center
  font-size: 12px
  color: var(--rapo-muted)
</style>
