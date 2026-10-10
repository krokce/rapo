<template>
  <div
    class="dashboard-panel column no-wrap"
    :class="{ 'dashboard-panel--over': over, 'dashboard-panel--dragging': dragging, 'dashboard-panel--tall': panel.height }"
    :style="{ '--span': panel.width, '--min': `${panel.minWidth || 0}px`, '--height': `${panel.height || 0}px` }"
    :draggable="handleDown"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
    @dragover="onDragOver"
    @dragleave="over = false"
    @drop="onDrop">
    <div class="dashboard-panel__head row no-wrap items-center">
      <q-icon
        name="fas fa-grip-vertical"
        size="11px"
        class="dashboard-panel__handle q-mr-sm"
        title="Drag to move within the section"
        @mousedown="handleDown = true"
        @mouseup="handleDown = false" />
      <div class="dashboard-panel__title ellipsis">{{ panel.title }}</div>
      <div v-if="$slots.facts" class="dashboard-panel__facts row no-wrap items-center q-ml-sm ellipsis">
        <slot name="facts" />
      </div>
      <q-space />
      <slot name="actions" />
      <q-btn flat round dense size="xs" icon="fas fa-ellipsis-v" color="grey-6" class="q-ml-xs" :aria-label="`${panel.title}: panel menu`">
        <q-menu anchor="bottom right" self="top right">
          <q-list dense style="min-width: 150px">
            <q-item v-close-popup clickable :disable="first" @click="$emit('move', -1)">
              <q-item-section avatar><q-icon name="fas fa-arrow-up" size="12px" /></q-item-section>
              <q-item-section>Move up</q-item-section>
            </q-item>
            <q-item v-close-popup clickable :disable="last" @click="$emit('move', 1)">
              <q-item-section avatar><q-icon name="fas fa-arrow-down" size="12px" /></q-item-section>
              <q-item-section>Move down</q-item-section>
            </q-item>
            <q-separator />
            <q-item v-close-popup clickable @click="$emit('hide')">
              <q-item-section avatar><q-icon name="fas fa-eye-slash" size="12px" /></q-item-section>
              <q-item-section>Hide</q-item-section>
            </q-item>
          </q-list>
        </q-menu>
      </q-btn>
    </div>
    <div class="dashboard-panel__body col">
      <div v-if="error" class="dashboard-panel__note row no-wrap items-center">
        <q-icon name="fas fa-exclamation-triangle" color="red-6" class="q-mr-sm" />
        <span class="ellipsis-2-lines" :title="error">Could not be loaded: {{ error }}</span>
      </div>
      <template v-else-if="loading">
        <q-skeleton type="rect" :height="`${skeletonHeight}px`" />
      </template>
      <div v-else-if="empty" class="dashboard-panel__note row no-wrap items-center">
        <q-icon :name="emptyIcon" class="q-mr-sm" />{{ empty }}
      </div>
      <slot v-else />
    </div>
  </div>
</template>

<script>
// The panel being dragged, which a panel of another section does not take.
let dragged = null;

// One panel of the Dashboard: its title and facts, actions and the menu (move, hide), then its chart, a skeleton while
// its part loads, its error, or a note when there is nothing to show. Dragged by its handle onto another panel of its
// section, it takes that panel's place (`drop`).
export default {
  name: "DashboardPanel",
  props: {
    panel: { type: Object, required: true },
    first: { type: Boolean, default: false },
    last: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    error: { type: String, default: null },
    // The note shown instead of the content, e.g. "No runs in this span."
    empty: { type: String, default: null },
    emptyIcon: { type: String, default: "fas fa-info-circle" },
    skeletonHeight: { type: Number, default: 180 },
  },
  emits: ["move", "hide", "drop"],
  data() {
    return { handleDown: false, dragging: false, over: false };
  },
  methods: {
    onDragStart(event) {
      dragged = this.panel;
      this.dragging = true;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", this.panel.id);
    },
    onDragEnd() {
      dragged = null;
      this.dragging = false;
      this.handleDown = false;
    },
    onDragOver(event) {
      if (dragged && dragged.section === this.panel.section && dragged.id !== this.panel.id) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        this.over = true;
      }
    },
    onDrop(event) {
      this.over = false;
      if (dragged && dragged.section === this.panel.section && dragged.id !== this.panel.id) {
        event.preventDefault();
        this.$emit("drop", dragged.id);
      }
    },
  },
};
</script>

<style scoped>
/* A share of the row in sixths of its width less the gaps (12px, DashboardPage), growing by the same share into what the
   row leaves: a row is always full. Below its minimum a panel wraps, and takes the whole row at most. */
.dashboard-panel {
  flex: var(--span) 1 calc((100% - 60px) * var(--span) / 6 + (var(--span) - 1) * 12px);
  min-width: min(var(--min), 100%);
  min-height: var(--height);
  padding: 6px 10px 8px;
  border: 1px solid var(--rapo-panel-border);
  border-radius: 6px;
  background: var(--rapo-surface);
}

.dashboard-panel--dragging {
  opacity: 0.5;
}

.dashboard-panel--over {
  outline: 2px dashed var(--rapo-teal);
  outline-offset: 2px;
}

.dashboard-panel__head {
  min-height: 24px;
  margin-bottom: 4px;
}

.dashboard-panel__handle {
  color: var(--rapo-label);
  cursor: grab;
  opacity: 0.5;
}

.dashboard-panel:hover .dashboard-panel__handle {
  opacity: 1;
}

.dashboard-panel__title {
  font-size: 14px;
  font-weight: 500;
  color: var(--rapo-header-text);
}

.dashboard-panel__facts {
  font-size: 12px;
  color: var(--rapo-muted);
  gap: 8px;
}

.dashboard-panel__body {
  min-height: 0;
}

/* A panel with a height gives it to its content (tiles that stretch to fill it). */
.dashboard-panel--tall .dashboard-panel__body {
  display: flex;
  flex-direction: column;
}

.dashboard-panel--tall .dashboard-panel__body > :deep(*) {
  flex: 1 1 auto;
  min-height: 0;
}

.dashboard-panel__note {
  min-height: 64px;
  font-size: 13px;
  color: var(--rapo-muted);
}
</style>
