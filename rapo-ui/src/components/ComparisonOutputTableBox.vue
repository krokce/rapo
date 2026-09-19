<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Select output columns</q-item-label>
      </q-item-section>

      <q-card-section class="q-gutter-xs">
        <div class="row q-gutter-xs items-center" v-for="(item, index) in cmpOutputTable" v-bind:key="index">
          <q-select
            use-input
            hide-selected
            fill-input
            class="col-3"
            outlined
            clearable
            @filter="filterFieldListA"
            v-model="cmpOutputTable[index].column_a"
            :options="datasourceAList"
            label="Field A" />

          <q-icon name="fas fa-circle" size="15px" color="blue-grey-3" />

          <q-select
            use-input
            hide-selected
            fill-input
            class="col-3"
            outlined
            clearable
            @filter="filterFieldListB"
            v-model="cmpOutputTable[index].column_b"
            :options="datasourceBList"
            label="Field B" />

          <q-icon name="fas fa-circle" size="15px" color="blue-grey-3" />

          <q-input use-input fill-input class="col-3" outlined clearable v-model="cmpOutputTable[index].column" label="Name (optional)" />

          <q-btn size="sm" color="primary" flat round icon="fas fa-minus" @click="removeCorrelationConfig(index)" />
          <q-btn v-if="index == cmpOutputTable.length - 1" size="sm" color="primary" flat round icon="fas fa-plus" @click="addColumn" />
        </div>
        <q-btn
          v-if="!cmpOutputTable || cmpOutputTable.length == 0"
          size="md"
          color="primary"
          icon="fas fa-plus"
          label="Add column"
          @click="addColumn" />
      </q-card-section>
    </q-card>
  </div>
</template>

<script>
import columnFilter from "../mixins/columnFilter";

// Output columns of a comparison (CMP) control: a column from A and/or B with an optional output name.
// modelValue is the parent's array and is edited in place.
export default {
  mixins: [columnFilter],
  props: {
    modelValue: { type: Array, required: true },
    datasourceAColumns: Array,
    datasourceBColumns: Array,
  },
  computed: {
    cmpOutputTable() {
      return this.modelValue;
    },
  },
  methods: {
    addColumn() {
      this.cmpOutputTable.push({ column_a: null, column_b: null, column: null });
    },
    removeCorrelationConfig(index) {
      this.cmpOutputTable.splice(index, 1);
    },
  },
};
</script>

<style></style>
