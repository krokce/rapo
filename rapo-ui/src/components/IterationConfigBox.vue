<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Iteration config</q-item-label>
      </q-item-section>

      <q-card-section class="q-gutter-xs">
        <div class="row q-gutter-xs items-center" v-for="(item, index) in iterationConfigObject" v-bind:key="index">
          <q-input outlined class="col-1" v-model.number="iterationConfigObject[index].iteration_id" type="number" label="Iteration" />
          <q-input outlined class="col-3" v-model.number="iterationConfigObject[index].iteration_description" label="Description" />
          <q-input outlined class="col-2" v-model.number="iterationConfigObject[index].period_back" type="number" label="Periods back">
            <template v-slot:prepend>
              <q-icon name="fas fa-history" @click.stop.prevent />
            </template>
          </q-input>
          <q-input class="col-2" v-model.number="iterationConfigObject[index].period_number" type="number" outlined label="Number of periods">
            <template v-slot:prepend>
              <q-icon name="fas fa-calendar-day" @click.stop.prevent />
            </template>
          </q-input>
          <q-select
            class="col-2"
            outlined
            emit-value
            map-options
            v-model="iterationConfigObject[index].period_type"
            :options="[
              { label: 'Day', value: 'D' },
              { label: 'Week', value: 'W' },
              { label: 'Month', value: 'M' },
            ]"
            label="Period type" />
          <q-select
            class="col-1"
            outlined
            emit-value
            map-options
            v-model="iterationConfigObject[index].status"
            :options="[
              { label: 'Yes', value: 'Y' },
              { label: 'No', value: 'N' },
            ]"
            label="Active" />
          <q-btn size="sm" color="primary" flat round icon="fas fa-minus" @click="removeIterationConfig(index)" />
          <q-btn
            v-if="index == iterationConfigObject.length - 1"
            size="sm"
            color="primary"
            flat
            round
            icon="fas fa-plus"
            @click="addIterationConfig(index + 2)" />
        </div>
        <q-btn v-if="iterationConfigObject.length == 0" size="md" color="primary" icon="fas fa-plus" label="Add run iteration" @click="addIterationConfig(1)" />
      </q-card-section>
    </q-card>
  </div>
</template>

<script>
export default {
  props: ["modelValue", "pb"],
  emits: ["update:modelValue"],
  data() {
    return {
      iterationConfigObject: this.modelValue,
      datasourceAList: null,
      datasourceBList: null,
    };
  },
  methods: {
    addIterationConfig(id) {
      this.iterationConfigObject.push({
        iteration_id: id,
        iteration_description: "Iteration #" + id,
        period_back: Number(this.pb)+id,
        period_number: 1,
        period_type: "D",
        status: "Y",
      });
    },
    removeIterationConfig(index) {
      this.iterationConfigObject.splice(index, 1);
    },
  },
  watch: {
    iterationConfigObject(newValue) {
      this.$emit("update:modelValue", newValue);
    },
    modelValue(newValue) {
      this.iterationConfigObject = newValue;
    },
  },
};
</script>

<style></style>
