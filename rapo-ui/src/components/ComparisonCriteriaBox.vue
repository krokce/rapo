<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>{{ title }}</q-item-label>
      </q-item-section>

      <q-card-section class="q-gutter-xs">
        <div class="row q-gutter-xs items-center" v-for="(item, index) in criteria" v-bind:key="index">
          <q-select
            use-input
            hide-selected
            fill-input
            class="col-4"
            outlined
            @filter="filterFieldListA"
            v-model="item.column_a"
            :options="datasourceAList"
            label="Field A" />

          <q-icon :name="icon" size="20px" color="blue-grey-3" />

          <q-select
            use-input
            hide-selected
            fill-input
            class="col-4"
            outlined
            @filter="filterFieldListB"
            v-model="item.column_b"
            :options="datasourceBList"
            label="Field B" />

          <q-btn size="sm" color="primary" flat round icon="fas fa-minus" @click="criteria.splice(index, 1)" />
          <q-btn v-if="index == criteria.length - 1" size="sm" color="primary" flat round icon="fas fa-plus" @click="addCriterion" />
        </div>
        <q-btn v-if="criteria.length == 0" size="md" color="primary" icon="fas fa-plus" :label="'Add ' + title.toLowerCase()" @click="addCriterion" />
      </q-card-section>
    </q-card>
  </div>
</template>

<script>
import columnFilter from "../mixins/columnFilter";

// Column pairs of a comparison (CMP) control: match criteria (rule_config) or mismatch criteria
// (error_definition). modelValue is the parent's array and is edited in place.
export default {
  mixins: [columnFilter],
  props: {
    modelValue: { type: Array, required: true },
    datasourceAColumns: Array,
    datasourceBColumns: Array,
    title: { type: String, required: true },
    icon: { type: String, default: "fas fa-equals" },
  },
  computed: {
    criteria() {
      return this.modelValue;
    },
  },
  methods: {
    addCriterion() {
      this.criteria.push({
        column_a: this.firstColumn(this.datasourceAColumns),
        column_b: this.firstColumn(this.datasourceBColumns),
      });
    },
  },
};
</script>
