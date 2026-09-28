<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>{{ title }}</q-item-label>
      </q-item-section>

      <q-card-section class="q-gutter-xs">
        <div class="row q-gutter-xs items-center" v-for="(item, index) in criteria" v-bind:key="index">
          <q-select
            v-if="!item.formula_mode"
            use-input
            hide-selected
            fill-input
            class="col-2"
            outlined
            @filter="filterFieldListA"
            v-model="item.column_a"
            :options="datasourceAList"
            label="Field A" />

          <q-input v-else outlined class="col-2" v-model="item.column_a" label="Field A">
            <template v-slot:append>
              <q-icon name="fas fa-calculator" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Always use 'a.' as prefix to DB fields in formula mode </q-tooltip>
          </q-input>

          <q-icon :name="icon" size="20px" color="blue-grey-3" />

          <q-select
            v-if="!item.formula_mode"
            use-input
            hide-selected
            fill-input
            class="col-2"
            outlined
            @filter="filterFieldListB"
            v-model="item.column_b"
            :options="datasourceBList"
            label="Field B" />

          <q-input v-else outlined class="col-2" v-model="item.column_b" label="Field B">
            <template v-slot:append>
              <q-icon name="fas fa-calculator" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Always use 'b.' as prefix to DB fields in formula mode </q-tooltip>
          </q-input>

          <q-icon name="fas fa-circle" size="15px" color="blue-grey-3" />

          <q-select
            class="col-1"
            outlined
            emit-value
            map-options
            :model-value="Boolean(item.formula_mode)"
            :options="[
              { label: 'Yes', value: true },
              { label: 'No', value: false },
            ]"
            label="Formula"
            @update:model-value="(value) => setFormulaMode(item, value)">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              In "Formula mode" you can use expressions instead of field names, e.g. "'0' || substr(a.MSISDN, 3)"
            </q-tooltip>
          </q-select>

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
import { fromFormula, toFormula } from "../utils/formula";

// Column pairs of a comparison (CMP) control: match criteria (rule_config) or mismatch criteria
// (error_definition). modelValue is the parent's array and is edited in place. In formula mode column_a/column_b
// are SQL expressions over the fetched tables aliased `a` and `b`.
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
        formula_mode: false,
      });
    },
    setFormulaMode(item, value) {
      item.formula_mode = value;
      if (value) {
        item.column_a = toFormula(item.column_a, "a.");
        item.column_b = toFormula(item.column_b, "b.");
      } else {
        item.column_a = fromFormula(item.column_a, "a.", this.datasourceAColumns);
        item.column_b = fromFormula(item.column_b, "b.", this.datasourceBColumns);
      }
    },
  },
};
</script>
