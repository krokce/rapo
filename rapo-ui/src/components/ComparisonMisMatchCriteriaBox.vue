<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Mismatch criteria</q-item-label>
      </q-item-section>

      <q-card-section class="q-gutter-xs">
        <div class="row q-gutter-xs items-center" v-for="(item, index) in ruleErrorObject" v-bind:key="index">
          <q-select
            use-input
            hide-selected
            fill-input
            class="col-4"
            outlined
            @filter="filterFieldListA"
            v-model="ruleErrorObject[index].column_a"
            :options="datasourceAList"
            label="Field A" />

          <q-icon name="fas fa-not-equal" size="20px" color="blue-grey-3" />

          <q-select
            use-input
            hide-selected
            fill-input
            class="col-4"
            outlined
            @filter="filterFieldListB"
            v-model="ruleErrorObject[index].column_b"
            :options="datasourceBList"
            label="Field B" />

          <q-btn size="sm" color="primary" flat round icon="fas fa-minus" @click="removeCorrelationConfig(index)" />
          <q-btn v-if="index == ruleErrorObject.length - 1" size="sm" color="primary" flat round icon="fas fa-plus" @click="addCorrelationConfig" />
        </div>
        <q-btn
          v-if="!ruleErrorObject || ruleErrorObject.length == 0"
          size="md"
          color="primary"
          icon="fas fa-plus"
          label="Add match criteria"
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
      ruleErrorObject: this.modelValue,
      datasourceAList: null,
      datasourceBList: null,
    };
  },
  methods: {
    addCorrelationConfig() {
      this.ruleErrorObject.push({
        column_a: this.datasourceAColumns[0],
        column_b: this.datasourceBColumns[0],
      });
    },
    removeCorrelationConfig(index) {
      this.ruleErrorObject.splice(index, 1);
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
  },
  watch: {
    ruleErrorObject(newValue) {
      this.$emit("update:modelValue", newValue);
    },
    modelValue(newValue) {
      this.ruleErrorObject = newValue;
    },
  },
  mounted() {
    if (!Array.isArray(this.ruleErrorObject) || this.ruleErrorObject.length === 0) {
      this.ruleErrorObject = [];
    }
  },
};
</script>

<style></style>
