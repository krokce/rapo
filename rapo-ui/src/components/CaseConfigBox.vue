<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Case config</q-item-label>
      </q-item-section>

      <q-card-section class="q-gutter-xs">
        <div class="row q-gutter-xs items-center" v-for="(item, index) in caseConfigObject" v-bind:key="index">
          <q-input outlined class="col-1" v-model.number="caseConfigObject[index].case_id" type="number" label="Case ID">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Map to this id below in "Case mapping". <br />Value will be written in RAPO_RESULT_KEY column in the discrepancy table.
            </q-tooltip>
          </q-input>
          <q-input outlined class="col-3" v-model.number="caseConfigObject[index].case_value" label="Value">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Name of the case e.g. "Customer not defined". <br />Value will be written in RAPO_RESULT_VALUE column in the discrepancy table.
            </q-tooltip>
          </q-input>
          <q-input outlined class="col-2" v-model.number="caseConfigObject[index].case_type" label="Type">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Case type e.g. "Error". <br />Value will be written in RAPO_RESULT_TYPE column in the discrepancy table.
            </q-tooltip>
          </q-input>
          <q-input outlined class="col-4" v-model.number="caseConfigObject[index].case_description" label="Description">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Case description for documentation purpose. <br />Used and visible only here in control config.
            </q-tooltip>
          </q-input>

          <q-btn size="sm" color="primary" flat round icon="fas fa-minus" @click="removeCaseConfig(index)" />
          <q-btn v-if="index == caseConfigObject.length - 1" size="sm" color="primary" flat round icon="fas fa-plus" @click="addCaseConfig(index + 2)" />
        </div>
        <q-btn v-if="caseConfigObject.length == 0" size="md" color="primary" icon="fas fa-plus" label="Add case definition" @click="addCaseConfig(1)" />
      </q-card-section>
    </q-card>
  </div>
</template>

<script>
export default {
  props: ["modelValue"],
  emits: ["update:modelValue"],
  data() {
    return {
      caseConfigObject: this.modelValue,
      datasourceAList: null,
      datasourceBList: null,
    };
  },
  methods: {
    addCaseConfig(id) {
      this.caseConfigObject.push({
        case_id: id,
        case_value: null,
        case_type: "Error",
        case_description: null,
      });
    },
    removeCaseConfig(index) {
      this.caseConfigObject.splice(index, 1);
    },
  },
  watch: {
    caseConfigObject(newValue) {
      this.$emit("update:modelValue", newValue);
    },
    modelValue(newValue) {
      this.caseConfigObject = newValue;
    },
  },
};
</script>

<style></style>
