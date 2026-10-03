<template>
  <div class="sparkline" @mousemove="hover" @mouseleave="hoverIndex = null">
    <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" preserveAspectRatio="none" class="sparkline-svg">
      <line v-if="thresholdY !== null" class="sparkline-threshold" x1="0" :x2="WIDTH" :y1="thresholdY" :y2="thresholdY" />
      <path v-if="paths[0]" class="sparkline-area" :class="levelClass" :d="paths[0].area" />
      <path v-for="(path, index) in paths" :key="index" class="sparkline-line" :class="[`sparkline-line-${index}`, index ? '' : levelClass]" :d="path.line" />
    </svg>
    <div v-if="hovered" class="sparkline-cursor" :style="{ left: `${hovered.x}%` }" />
    <div v-if="hovered" class="sparkline-tip" :class="hovered.x > 50 ? 'sparkline-tip-left' : ''" :style="{ left: `${hovered.x}%` }">
      <div class="text-weight-medium">{{ hovered.time }}</div>
      <div v-for="item in hovered.values" :key="item.label">{{ item.label }} {{ item.text }}</div>
    </div>
  </div>
</template>

<script>
const WIDTH = 200;
const HEIGHT = 40;

// A time chart of sampled points, stretched to the box its parent gives it (at least 40px high): x is time over the
// window ending at `end`, so the history of a restarted server starts where it started, and a missed sample (longer
// than 2.5 intervals) breaks the line.
export default {
  name: "HealthSparkline",
  props: {
    points: { type: Array, required: true },
    // [{field, label}], the first one filled.
    series: { type: Array, required: true },
    end: { type: Number, required: true },
    windowMs: { type: Number, required: true },
    intervalMs: { type: Number, required: true },
    max: { type: Number, default: null },
    threshold: { type: Number, default: null },
    level: { type: String, default: null },
    format: { type: Function, required: true },
  },
  data() {
    return { WIDTH, HEIGHT, hoverIndex: null };
  },
  computed: {
    times() {
      return this.points.map((point) => new Date(point.t).getTime());
    },
    top() {
      if (this.max) {
        return this.max;
      }
      let top = this.threshold || 0;
      this.points.forEach((point) => this.series.forEach(({ field }) => (top = Math.max(top, Number(point[field]) || 0))));
      // Some headroom, and a count of 0 or 1 never fills the whole height.
      return Math.max(top * 1.15, 1);
    },
    paths() {
      const start = this.end - this.windowMs;
      const x = (time) => ((time - start) / this.windowMs) * WIDTH;
      const y = (value) => HEIGHT - 1 - (Math.min(Math.max(value, 0), this.top) / this.top) * (HEIGHT - 2);
      return this.series.map(({ field }) => {
        let line = "";
        let area = "";
        let runStart = null;
        let previous = null;
        const close = () => {
          if (runStart !== null) {
            area += `L${previous.toFixed(1)},${HEIGHT}L${runStart.toFixed(1)},${HEIGHT}Z`;
          }
          runStart = null;
        };
        this.points.forEach((point, index) => {
          const value = point[field];
          const time = this.times[index];
          const gap = index && time - this.times[index - 1] > this.intervalMs * 2.5;
          if (value === null || value === undefined || time < start) {
            close();
            return;
          }
          if (gap) {
            close();
          }
          const px = x(time);
          const py = y(Number(value));
          const command = runStart === null ? "M" : "L";
          line += `${command}${px.toFixed(1)},${py.toFixed(1)}`;
          area += runStart === null ? `M${px.toFixed(1)},${HEIGHT}L${px.toFixed(1)},${py.toFixed(1)}` : `L${px.toFixed(1)},${py.toFixed(1)}`;
          if (runStart === null) {
            runStart = px;
          }
          previous = px;
        });
        close();
        return line ? { line, area } : null;
      }).filter(Boolean);
    },
    thresholdY() {
      if (this.threshold === null || this.threshold > this.top) {
        return null;
      }
      return HEIGHT - 1 - (this.threshold / this.top) * (HEIGHT - 2);
    },
    levelClass() {
      return this.level ? `sparkline-${this.level}` : "";
    },
    hovered() {
      if (this.hoverIndex === null || !this.points[this.hoverIndex]) {
        return null;
      }
      const point = this.points[this.hoverIndex];
      const x = ((this.times[this.hoverIndex] - (this.end - this.windowMs)) / this.windowMs) * 100;
      return {
        x: Math.min(Math.max(x, 0), 100),
        time: point.t.slice(11, 19),
        values: this.series.map(({ field, label }) => ({ label, text: this.format(point[field]) })),
      };
    },
  },
  methods: {
    // The point nearest to the mouse in time.
    hover(event) {
      const box = event.currentTarget.getBoundingClientRect();
      const time = this.end - this.windowMs + ((event.clientX - box.left) / box.width) * this.windowMs;
      let best = null;
      let distance = Infinity;
      this.times.forEach((value, index) => {
        if (Math.abs(value - time) < distance) {
          distance = Math.abs(value - time);
          best = index;
        }
      });
      this.hoverIndex = best;
    },
  },
};
</script>

<style lang="sass">
.sparkline
  position: relative
  min-height: 40px

.sparkline-svg
  position: absolute
  inset: 0
  display: block
  width: 100%
  height: 100%
  overflow: visible

.sparkline-line
  fill: none
  stroke-width: 1.5
  stroke-linejoin: round
  vector-effect: non-scaling-stroke
  stroke: var(--rapo-spark)

  &.sparkline-line-1
    stroke: var(--rapo-spark-2)
    stroke-dasharray: 3 2

  &.sparkline-warn
    stroke: var(--rapo-warn)
  &.sparkline-crit
    stroke: var(--rapo-crit)

.sparkline-area
  fill: var(--rapo-spark-soft)
  stroke: none

  &.sparkline-warn
    fill: var(--rapo-warn-soft)
  &.sparkline-crit
    fill: var(--rapo-crit-soft)

.sparkline-threshold
  stroke: var(--rapo-warn)
  stroke-width: 1
  stroke-dasharray: 2 3
  vector-effect: non-scaling-stroke
  opacity: 0.7

.sparkline-cursor
  position: absolute
  top: 0
  bottom: 0
  width: 1px
  background: var(--rapo-muted)
  pointer-events: none

.sparkline-tip
  position: absolute
  top: 2px
  margin-left: 6px
  padding: 3px 6px
  border-radius: 3px
  background: var(--rapo-header-text)
  color: var(--rapo-surface)
  font-size: 11px
  line-height: 1.35
  white-space: nowrap
  pointer-events: none
  z-index: 2

  &.sparkline-tip-left
    transform: translateX(-100%)
    margin-left: -6px
</style>
