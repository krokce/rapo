<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Mismatch criteria (discrepancy config)</q-item-label>
      </q-item-section>

      <q-card-section class="q-gutter-xs">
        <div class="row q-gutter-xs items-center" v-for="(item, index) in ruleConfigObject.discrepancy_config" v-bind:key="index">
          <q-select
            v-if="!ruleConfigObject.discrepancy_config[index].formula_mode"
            use-input
            hide-selected
            fill-input
            class="col-2"
            outlined
            @filter="filterFieldListA"
            v-model="ruleConfigObject.discrepancy_config[index].field_a"
            :options="datasourceAList"
            label="Field A" />

          <q-input
            v-if="ruleConfigObject.discrepancy_config[index].formula_mode"
            outlined
            class="col-2"
            v-model="ruleConfigObject.discrepancy_config[index].field_a"
            label="Field A">
            <template v-slot:append>
              <q-icon name="fas fa-calculator" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Aways use 'a.' as prefix to DB fields in formula mode </q-tooltip>
          </q-input>

          <q-icon name="fas fa-equals" size="20px" color="blue-grey-3" />

          <q-select
            v-if="!ruleConfigObject.discrepancy_config[index].formula_mode"
            use-input
            hide-selected
            fill-input
            class="col-2"
            outlined
            @filter="filterFieldListB"
            v-model="ruleConfigObject.discrepancy_config[index].field_b"
            :options="datasourceBList"
            label="Field B" />

          <q-input
            v-if="ruleConfigObject.discrepancy_config[index].formula_mode"
            outlined
            class="col-2"
            v-model="ruleConfigObject.discrepancy_config[index].field_b"
            label="Field B">
            <template v-slot:append>
              <q-icon name="fas fa-calculator" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Always use 'b.' as prefix to DB fields in formula mode </q-tooltip>
          </q-input>

          <q-icon name="fas fa-circle" size="15px" color="blue-grey-3" />

          <q-input
            outlined
            class="col-1"
            v-model.number="ruleConfigObject.discrepancy_config[index].numeric_tolerance_from"
            type="number"
            step="0.1"
            label="Tolerance from">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Lower tolerance value (match if A minus B is greater than this value) </q-tooltip>
          </q-input>

          <q-input
            outlined
            class="col-1"
            v-model.number="ruleConfigObject.discrepancy_config[index].numeric_tolerance_to"
            type="number"
            step="0.1"
            label="Tolerance to">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Upper tolerance value (match if A minus B is lower than this value) </q-tooltip>
          </q-input>

          <q-icon name="fas fa-circle" size="15px" color="blue-grey-3" />

          <q-select
            class="col-1"
            outlined
            emit-value
            map-options
            v-model="ruleConfigObject.discrepancy_config[index].percentage_mode"
            :options="[
              { label: 'Yes', value: true },
              { label: 'No', value: false },
            ]"
            label="Percentage">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              In "Percentage mode" the difference incl. tolerance values will be treated as percentages
            </q-tooltip>
          </q-select>

          <q-icon name="fas fa-circle" size="15px" color="blue-grey-3" />

          <q-select
            class="col-1"
            outlined
            emit-value
            map-options
            v-model="ruleConfigObject.discrepancy_config[index].formula_mode"
            :options="[
              { label: 'Yes', value: true },
              { label: 'No', value: false },
            ]"
            label="Formula"
            @update:model-value="
              (value) => {
                ruleConfigObject.discrepancy_config[index].formula_mode = value;
                if (value) {
                  ruleConfigObject.discrepancy_config[index].formula_alias = ruleConfigObject.discrepancy_config[index].field_a;
                  ruleConfigObject.discrepancy_config[index].field_a = 'a.' + ruleConfigObject.discrepancy_config[index].field_a;
                  ruleConfigObject.discrepancy_config[index].field_b = 'b.' + ruleConfigObject.discrepancy_config[index].field_b;
                } else {
                  ruleConfigObject.discrepancy_config[index].field_a = null;
                  ruleConfigObject.discrepancy_config[index].field_b = null;
                }
              }
            ">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              In "Formula mode" you can use expressions instead of field names, e.g. "a.AMOUNT + a.TAX"
            </q-tooltip>
          </q-select>
          <q-input
            v-if="ruleConfigObject.discrepancy_config[index].formula_mode"
            outlined
            class="col-2"
            v-model="ruleConfigObject.discrepancy_config[index].formula_alias"
            label="Formula alias">
            <template v-slot:prepend>
              <q-icon name="fas fa-font" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Name to be used when presenting the discrepancies </q-tooltip>
          </q-input>

          <q-btn size="sm" color="primary" flat round icon="fas fa-minus" @click="removeCorrelationConfig(index)" />
          <q-btn
            v-if="index == ruleConfigObject.discrepancy_config.length - 1"
            size="sm"
            color="primary"
            flat
            round
            icon="fas fa-plus"
            @click="addCorrelationConfig" />
        </div>
        <q-btn
          v-if="ruleConfigObject.discrepancy_config.length == 0"
          size="md"
          color="primary"
          icon="fas fa-plus"
          label="Add mis-match criteria"
          @click="addCorrelationConfig" />
      </q-card-section>
    </q-card>
  </div>
</template>

<script>
export default {
  props: ["modelValue", "datasourceAColumns", "datasourceBColumns"],
  emits: ["update:modelValue"],
  data() {
    return {
      ruleConfigObject: this.modelValue,
      datasourceAList: null,
      datasourceBList: null,
    };
  },
  methods: {
    addCorrelationConfig() {
      this.ruleConfigObject.discrepancy_config.push({
        field_a: this.datasourceAColumns[0],
        field_b: this.datasourceBColumns[0],
        numeric_tolerance_from: 0,
        numeric_tolerance_to: 0,
        percentage_mode: false,
        formula_mode: false,
        formula_alias: null,
      });
    },
    removeCorrelationConfig(index) {
      this.ruleConfigObject.discrepancy_config.splice(index, 1);
    },
    filterFieldListA(val, update, abort) {
      if (val.length < 0) {
        abort();
        return;
      }

      update(() => {
        const needle = val.toLowerCase();
        this.datasourceAList = this.datasourceAColumns.filter((v) => v.toLowerCase().indexOf(needle) > -1);
      });
    },
    filterFieldListB(val, update, abort) {
      if (val.length < 0) {
        abort();
        return;
      }

      update(() => {
        const needle = val.toLowerCase();
        this.datasourceBList = this.datasourceBColumns.filter((v) => v.toLowerCase().indexOf(needle) > -1);
      });
    },
    onNewValue(index, field) {
      // Handle new value creation logic here
      console.log(`New value added for index ${index}, field ${field}`);
    },
  },
  watch: {
    ruleConfigObject(newValue) {
      this.$emit("update:modelValue", newValue);
    },
    modelValue(newValue) {
      this.ruleConfigObject = newValue;
    },
  },
};
</script>

<style></style>
