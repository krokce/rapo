<template>
  <q-dialog v-model="shown">
    <q-card style="width: 760px; max-width: 95vw">
      <q-card-section>
        <div class="text-h6">SQL filter</div>
        <div class="text-caption text-grey-7">
          A condition over the dataset's columns, applied by the database: the sample is fetched again from the matching records only, e.g.
          <code>amount &gt; 100 and call_type in ('MOC', 'MTC')</code>. Leave it empty to remove the filter.
        </div>
      </q-card-section>
      <q-card-section class="q-pt-none">
        <code-box v-model="text" label="Where" :columns="columnNames" :check="check" />
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat no-caps color="grey-8" label="Cancel" />
        <q-btn unelevated no-caps color="primary" icon="fas fa-database" label="Load from database" @click="apply" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import CodeBox from "../CodeBox.vue";
import { api } from "../../api";

// The raw WHERE of a pushdown, checked by Oracle (validate-analysis-where) before it is used.
export default {
  name: "SqlFilterDialog",
  components: { CodeBox },
  props: {
    processId: { type: [Number, String], required: true },
    dataset: { type: String, required: true },
    columns: { type: Array, default: () => [] },
  },
  emits: ["apply"],
  data() {
    return { shown: false, text: "" };
  },
  computed: {
    columnNames() {
      return this.columns.map((column) => column.name.toUpperCase());
    },
  },
  methods: {
    open(where) {
      this.text = where || "";
      this.shown = true;
    },
    check(text) {
      return api("validate-analysis-where", {
        method: "POST",
        params: { process_id: this.processId, dataset: this.dataset },
        body: { where: text },
        loadingBar: false,
      });
    },
    apply() {
      this.shown = false;
      this.$emit("apply", (this.text || "").trim());
    },
  },
};
</script>
