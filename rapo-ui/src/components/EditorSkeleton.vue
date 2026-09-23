<template>
  <q-card>
    <q-skeleton type="rect" height="48px" square animation="fade" />
    <q-card-section class="q-pa-lg">
      <div v-for="row in rows" :key="row" class="row q-col-gutter-md q-mb-lg">
        <div v-for="field in 3" :key="field" class="col">
          <q-skeleton type="QInput" animation="fade" />
        </div>
      </div>
      <q-skeleton type="QInput" height="120px" animation="fade" />
    </q-card-section>
  </q-card>
</template>

<script>
// Placeholder for an editor card (tabs bar and form) until the record it edits has loaded.
export default {
  props: {
    rows: { type: Number, default: 4 },
  },
};
</script>
