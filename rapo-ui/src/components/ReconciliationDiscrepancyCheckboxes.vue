<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Discrepancies</q-item-label>
      </q-item-section>

      <q-card-section class="row q-gutter-sm">
        <q-checkbox
          size="lg"
          color="blue"
          class="col-2"
          label="Write A not in B discrepancies"
          v-model="ruleConfigObject.need_issues_a"
          @click="
            ruleConfigObject.output_limit_a = ruleConfigObject.need_issues_a || ruleConfigObject.need_recons_a ? ruleConfigObject.output_limit_a : null
          " />

        <q-checkbox
          size="lg"
          color="blue"
          class="col-2"
          label="Write A matches"
          v-model="ruleConfigObject.need_recons_a"
          @click="
            ruleConfigObject.output_limit_a = ruleConfigObject.need_issues_a || ruleConfigObject.need_recons_a ? ruleConfigObject.output_limit_a : null
          " />

        <q-input
          v-if="ruleConfigObject.need_issues_a || ruleConfigObject.need_recons_a"
          class="col-2"
          v-model.number="ruleConfigObject.output_limit_a"
          type="number"
          outlined
          label="Output limit A">
          <template v-slot:prepend>
            <q-icon name="fas fa-list-ol" @click.stop.prevent />
          </template>
          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
            Limit the number of records in the output table. <br />Leave empty for no limit.
          </q-tooltip>
        </q-input>
      </q-card-section>

      <q-card-section class="row q-gutter-sm">
        <q-checkbox
          size="lg"
          color="blue"
          class="col-2"
          label="Write B not in A discrepancies"
          v-model="ruleConfigObject.need_issues_b"
          @click="
            ruleConfigObject.output_limit_b = ruleConfigObject.need_issues_b || ruleConfigObject.need_recons_b ? ruleConfigObject.output_limit_b : null
          " />

        <q-checkbox
          size="lg"
          color="blue"
          class="col-2"
          label="Write B matches"
          v-model="ruleConfigObject.need_recons_b"
          @click="
            ruleConfigObject.output_limit_b = ruleConfigObject.need_issues_b || ruleConfigObject.need_recons_b ? ruleConfigObject.output_limit_b : null
          " />

        <q-input
          v-if="ruleConfigObject.need_issues_b || ruleConfigObject.need_recons_b"
          class="col-2"
          v-model.number="ruleConfigObject.output_limit_b"
          type="number"
          outlined
          label="Output limit B">
          <template v-slot:prepend>
            <q-icon name="fas fa-list-ol" @click.stop.prevent />
          </template>
          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
            Limit the number of records in the output table. <br />Leave empty for no limit.
          </q-tooltip>
        </q-input>
      </q-card-section>

      <q-card-section class="row q-gutter-sm">
        <q-checkbox size="lg" class="col-2" color="blue" label="Allow duplicates" v-model="ruleConfigObject.allow_duplicates">
          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 0]"> If active, duplicate records won't be treated as discrepancies </q-tooltip>
        </q-checkbox>
      </q-card-section>
    </q-card>

    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Advanced</q-item-label>
      </q-item-section>

      <q-card-section class="row q-gutter-sm">
        <q-select
          class="col-2"
          outlined
          emit-value
          map-options
          :model-value="setting('fuzzy_optimization')"
          :options="settingOptions('fuzzy_optimization')"
          @update:model-value="setSetting('fuzzy_optimization', $event)"
          label="Fuzzy optimization">
          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
            Reconciliation parameter that allows to join records within a correlation cluster of the same dimension (1k1, 2k2, 3k3, etc.) using a simple
            positional method with sorting by the sum of numerical values.
            <br />Such clusters are formed if the correlation keys do not provide a unique connection and several records on one side are connected to several
            records on the other.
          </q-tooltip>
        </q-select>

        <q-select
          class="col-2"
          outlined
          emit-value
          map-options
          :model-value="setting('discrepancy_matching')"
          :options="settingOptions('discrepancy_matching')"
          @update:model-value="setSetting('discrepancy_matching', $event)"
          label="Discrepancy matching">
          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 0]">
            Consider also mismatch criteria (discrepancy config) when identifying duplicates. If enabled and there is a discrepancy <br />
            above tolerance with the record on the other side the record will be marked as error instead of duplicate. <br />
            Useful together with the "Allow Duplicates" feature so that you identify duplicates that are actually errors,<br />
            and only ignore those that are successfully matched.
          </q-tooltip>
        </q-select>

        <q-select
          class="col-2"
          outlined
          emit-value
          map-options
          :model-value="setting('normalization_type')"
          :options="settingOptions('normalization_type')"
          @update:model-value="setSetting('normalization_type', $event)"
          label="Normalization">
          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
            Useful in cases where correlation keys do not guarantee a unique match, and distances <br />
            based on discrepancy config fields produce similar or identical values when summed. <br />
            <ul>
              <li>Rank: Replace numerical values with their rank (order) within the sorted dataset</li>
              <li>Min-Max: Scale numerical values to a 0-1 range based on the minimum and maximum values in the dataset</li>
              <li>Z-Score: Normalize numerical values based on their distance from the mean in terms of standard deviations</li>
              <li>Relative Distance: Use squared A->B distance relative to the defined discrepancy tolerance for ranking</li>
            </ul>
          </q-tooltip>
        </q-select>

        <q-select
          class="col-2"
          outlined
          emit-value
          map-options
          :model-value="setting('correlation_limit')"
          :options="settingOptions('correlation_limit')"
          @update:model-value="setSetting('correlation_limit', $event)"
          label="Correlation limit">
          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
            If active, the correlation dataset will be limited to x2.5 times of the larger datasource record-count to prevent huge resultsets caused by weak or
            missing match criteria (cross join)
            <br />Note that activating the correlation limit will likely result in up to 30% slower performance. Recomended to be used only during the
            development phase.
          </q-tooltip>
        </q-select>
      </q-card-section>
    </q-card>
  </div>
</template>

<script>
import { mapGetters } from "vuex";

const YES_NO = [
  { label: "Yes", value: true },
  { label: "No", value: false },
];

// Algorithm options of a rule_config. When one is unset the engine takes the [ALGORITHM] value from rapo.ini
// (served by /api/parameters), else its built-in default (Control parser); correlation_limit has no ini option.
const SETTINGS = {
  fuzzy_optimization: { options: YES_NO, builtIn: true, ini: true },
  discrepancy_matching: { options: YES_NO, builtIn: false, ini: true },
  normalization_type: {
    options: [
      { label: "None", value: "default" },
      { label: "Rank", value: "rank" },
      { label: "Min-Max", value: "minmax" },
      { label: "Z-Score", value: "z_norm" },
      { label: "Relative Distance", value: "srd" },
    ],
    builtIn: "default",
    ini: true,
  },
  correlation_limit: { options: YES_NO, builtIn: false, ini: false },
};

// q-select treats null as "nothing selected", so the "use the default" entry needs its own value.
const DEFAULT = "__default__";

// Output and matching options of a reconciliation (REC) rule_config. modelValue is the parent's rule_config
// object and is edited in place.
export default {
  props: {
    modelValue: { type: Object, required: true },
    control: { type: Object, required: true },
  },
  computed: {
    ...mapGetters(["getEnvParameters"]),
    ruleConfigObject() {
      return this.modelValue;
    },
  },
  methods: {
    setting(key) {
      const value = this.ruleConfigObject[key];
      // The engine reads "none" like "default" (no normalization); show it as the same option.
      if (key === "normalization_type" && value === "none") {
        return "default";
      }
      return value ?? DEFAULT;
    },
    // Unsetting removes the key, so the control keeps following rapo.ini.
    setSetting(key, value) {
      if (value === DEFAULT) {
        delete this.ruleConfigObject[key];
      } else {
        this.ruleConfigObject[key] = value;
      }
    },
    settingOptions(key) {
      const { options, builtIn, ini } = SETTINGS[key];
      const iniValue = ini && this.getEnvParameters ? this.getEnvParameters[key] : null;
      const effective = iniValue ?? builtIn;
      const label = (options.find((option) => option.value === effective) || { label: String(effective) }).label;
      return [{ label: `Default: ${label}${iniValue != null ? " (rapo.ini)" : ""}`, value: DEFAULT }, ...options];
    },
  },
  mounted() {
    // Older configs kept one output_limit for both sides.
    if (!this.ruleConfigObject.output_limit_a) {
      this.ruleConfigObject.output_limit_a = this.control.output_limit;
    }
    if (!this.ruleConfigObject.output_limit_b) {
      this.ruleConfigObject.output_limit_b = this.control.output_limit;
    }
  },
};
</script>

<style></style>
