<template>
  <div class="file-heatmap">
    <div class="file-heatmap__row file-heatmap__hours">
      <div class="file-heatmap__label"></div>
      <div v-for="hour in 24" :key="hour" class="file-heatmap__hour" :class="{ 'file-heatmap__hour--selected': selected === hour - 1 }">
        {{ String(hour - 1).padStart(2, "0") }}
      </div>
    </div>
    <div v-for="row in rows" :key="row.key" class="file-heatmap__row">
      <div class="file-heatmap__label ellipsis" :class="{ 'text-weight-bold': row.key === 'total' }">
        <q-icon v-if="row.color" name="fas fa-circle" :color="row.color" size="9px" class="q-mr-xs" />{{ row.label }}
      </div>
      <div
        v-for="(cell, hour) in row.cells"
        :key="hour"
        class="file-heatmap__cell"
        :class="{ 'file-heatmap__cell--errors': cell.errors, 'file-heatmap__cell--selected': selected === hour, 'file-heatmap__cell--dim': selected !== null && selected !== hour }"
        :style="{ background: color(cell.files, row.key === 'total') }"
        @click="$emit('select', selected === hour ? null : hour)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 6]">
          {{ String(hour).padStart(2, "0") }}:00–{{ String(hour + 1).padStart(2, "0") }}:00, {{ row.label }}: {{ cell.files.toLocaleString() }} file(s)<span
            v-if="cell.errors"
            >, {{ cell.errors }} error(s)</span
          >
        </q-tooltip>
      </div>
    </div>
  </div>
</template>

<script>
// Files per hour of the day (the database's clock): one row per lane and a Total, colored by count on a square-root
// scale up to the busiest cell. A cell with ERROR files has a red outline. A click picks the hour, a second clears it.
export default {
  name: "FileHeatmap",
  props: {
    // [{key, label, color, cells: [{files, errors}] x 24}] (utils/files.js heatmapRows).
    rows: { type: Array, required: true },
    selected: { type: Number, default: null },
  },
  emits: ["select"],
  computed: {
    // The busiest cell of the lanes; the Total row is scaled on its own, else it would wash the lanes out.
    maxima() {
      const lanes = this.rows.filter((row) => row.key !== "total").flatMap((row) => row.cells.map((cell) => cell.files));
      const total = this.rows.filter((row) => row.key === "total").flatMap((row) => row.cells.map((cell) => cell.files));
      return { lanes: Math.max(1, ...lanes), total: Math.max(1, ...total) };
    },
  },
  methods: {
    color(files, total = false) {
      if (!files) {
        return "#eceff1";
      }
      const share = Math.sqrt(files / (total ? this.maxima.total : this.maxima.lanes));
      const lightness = 92 - Math.min(share, 1) * 55;
      return `hsl(199, 80%, ${lightness}%)`;
    },
  },
};
</script>

<style scoped>
.file-heatmap {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  user-select: none;
}
.file-heatmap__row {
  display: grid;
  grid-template-columns: 110px repeat(24, minmax(0, 1fr));
  gap: 2px;
  align-items: center;
}
.file-heatmap__label {
  color: #546e7a;
  padding-right: 6px;
}
.file-heatmap__hour {
  text-align: center;
  color: #90a4ae;
}
.file-heatmap__hour--selected {
  color: #01579b;
  font-weight: bold;
}
.file-heatmap__cell {
  height: 16px;
  border-radius: 2px;
  cursor: pointer;
  box-sizing: border-box;
}
.file-heatmap__cell--errors {
  border: 2px solid #e53935;
}
.file-heatmap__cell--selected {
  outline: 2px solid #01579b;
  outline-offset: 1px;
}
.file-heatmap__cell--dim {
  opacity: 0.45;
}
</style>
