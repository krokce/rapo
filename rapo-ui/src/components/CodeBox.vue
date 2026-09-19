<template>
  <div>
    <span class="row items-center justify-between">
      <label>{{ label }}</label>
      <div>
        <q-btn v-if="code" class="col-auto" flat size="xs" icon="fas fa-times" @click="clearCode" />
        <q-btn class="col-auto" flat size="sm" label="Example">
          <q-menu>
            <q-list dense class="text-no-wrap">
              <q-item clickable v-close-popup v-for="menu in menuItems" :key="menu.menuText">
                <q-item-section @click="setCode(menu.exampleText)">
                  {{ menu.menuText }}
                </q-item-section>
              </q-item>
              <q-separator v-if="code" />
              <q-item clickable v-close-popup v-if="code">
                <q-item-section @click="clearCode"> Clear text </q-item-section>
              </q-item>
              <q-separator />
            </q-list>
          </q-menu>
        </q-btn>
      </div>
    </span>
    <codemirror ref="editor" v-model="code" :indent-with-tab="true" :smart-indent="true" :tab-size="4" :extensions="extensions" @ready="handleReady" />
  </div>
</template>

<script>
import { Codemirror } from "vue-codemirror";
import { EditorState } from "@codemirror/state";
import { sql } from "@codemirror/lang-sql";

// import { oneDark } from '@codemirror/theme-one-dark'
// import { HighlightStyle } from "@codemirror/language"

export default {
  props: ["modelValue", "label"],
  emits: ["update:modelValue"],
  components: {
    Codemirror,
  },
  data() {
    return {
      view: null,
      code: this.modelValue,
      placeholder: this.textPlaceholder,
      extensions: [sql(), EditorState.readOnly.of(false)],
      examples: {
        error_config: [
          { menuText: "Catch all (as error)", exampleText: "1=1" },
          {
            menuText: "ANL Sample conditions (using SQL-like syntax)",
            exampleText: "(charge != calc_charge or calc_charge is null) and imsi not in (select imsi from ds_imsi_whitelist)",
          },
          {
            menuText: "ANL Sample conditions (using JSON syntax)",
            exampleText:
              '[{"column": "CHARGE", "value": "CALC_CHARGE", "is_column": true}, {"connexion": "or", "column": "CALC_CHARGE", "relation": "is", "value": "NULL"}]',
          },
          {
            menuText: "REC Sample conditions (using JSON syntax)",
            exampleText: '[\n\t{"column_a": "case_type", "column_b": "case_type"}\n]',
          },
        ],
        rule_config: [
          {
            menuText: "REC Sample conditions (using JSON syntax)",
            exampleText: '[\n\t{"column_a":"posting_date","column_b":"posting_date"},\n\t{"column_a":"case_type","column_b":"case_type"}\n]',
          },
        ],
        case_config: [
          {
            menuText: "Basic 3 class example",
            exampleText:
              '[\n\t{\n\t\t"case_id": 1,\n\t\t"case_value": "Tariffication confirmed",\n\t\t"case_type": "Normal",\n\t\t"case_description": "Tariffication confirmed."\n\t},\n\t{\n\t\t"case_id": 2,\n\t\t"case_value": "Tariffication failed",\n\t\t"case_type": "Error",\n\t\t"case_description": "Tariffication failed."\n\t},\n\t{\n\t\t"case_id": 3,\n\t\t"case_value": "Tariffication not calculated",\n\t\t"case_type": "Warning",\n\t\t"case_description": "Tariffication not analysed."\n\t}\n]',
          },
        ],
        result_config: [
          {
            menuText: "Basic 3 class example",
            exampleText: "case\n\twhen charge = calc_charge then 1\n\twhen charge != calc_charge then 2\n\twhen calc_charge is null then 3\nend",
          },
        ],
        source_filter: [
          {
            menuText: "Basic filter example",
            exampleText: "service_id = 1 and direction_id = 1",
          },
          {
            menuText: "Subselect filter example",
            exampleText: "ftr_code in (\n\tselect feature_code \n\tfrom feature@amdocs \n\twhere ftr_expiration_date is null\n)",
          },
        ],
        preparation_sql: [
          {
            menuText: "Materialized view refresh",
            exampleText: "begin\n\tdbms_snapshot.refresh('MVIDS_ACTIVE_5G_HLR', 'c');\nend;",
          },
          {
            menuText: "Truncate and insert into table",
            exampleText:
              "begin\n\texecute immediate 'truncate table tmp_table';\n\tinsert into tmp_table select subscriber_no, ban, status_date from ds_subscribers where state = trunc(sysdate);\n\tcommit;\nend;",
          },
          {
            menuText: "Insert log line (using vars)",
            exampleText:
              "insert into log_sp_run\nvalues (\n    '{control_name} with PID: {process_id} executed for period from {control_date_from:%Y-%m-%d} to {control_date_to:%Y-%m-%d}', \n    'COMPLETE', \n    to_date('{control_date:%Y%m%d}', 'yyyymmdd'), \n    sysdate, \n    null, \n    null\n);"
          },
          {
            menuText: "Complex preparation example (using vars)",
            exampleText:
              "declare\n	check_value integer;\nbegin\n	execute immediate 'select count(*) from user_tables where table_name = ''TMP_{control_name}_{control_date:%Y%m%d}''' into check_value;\n	if check_value > 0 then\n		execute immediate 'drop table tmp_{control_name}_{control_date:%Y%m%d}';\n	end if;\n	execute immediate 'create table tmp_{control_name}_{control_date:%Y%m%d} as ' || 'select * from vids_rr6_pr_sms_dws ' || 'where charged_date >= trunc(sysdate)-7';\nend;",
          },
        ],
        prerequisite_sql: [
          {
            menuText: "Positive example (control will be executed)",
            exampleText: "select count(*) from vids_rr7_pr_mms_dws",
          },
          {
            menuText: "Negative example (control execution will be terminated)",
            exampleText: "select count(*) from vids_rr7_pr_mms_dws\nwhere 1=2",
          },
        ],
        completion_sql: [
          {
            menuText: "Materialized view refresh",
            exampleText: "begin\n\tdbms_snapshot.refresh('MVIDS_ACTIVE_5G_HLR', 'c');\nend;",
          },
          {
            menuText: "Truncate and insert into table",
            exampleText:
              "begin\n\texecute immediate 'truncate table tmp_table';\n\tinsert into tmp_table select subscriber_no, ban, status_date from ds_subscribers where state = trunc(sysdate);\n\tcommit;\nend;",
          },
          {
            menuText: "Insert log line (using vars)",
            exampleText:
              "insert into log_sp_run\nvalues (\n    '{control_name} with PID: {process_id} executed for period from {control_date_from:%Y-%m-%d} to {control_date_to:%Y-%m-%d}', \n    'COMPLETE', \n    to_date('{control_date:%Y%m%d}', 'yyyymmdd'), \n    sysdate, \n    null, \n    null\n);"
          },
          {
            menuText: "Complex completion example (using vars)",
            exampleText:
              "declare\n	check_value integer;\nbegin\n	execute immediate 'select count(*) from user_tables where table_name = ''TMP_{control_name}_{control_date:%Y%m%d}''' into check_value;\n	if check_value > 0 then\n		execute immediate 'drop table tmp_{control_name}_{control_date:%Y%m%d}';\n	end if;\n	execute immediate 'create table tmp_{control_name}_{control_date:%Y%m%d} as ' || 'select * from vids_rr6_pr_sms_dws ' || 'where charged_date >= trunc(sysdate)-7';\nend;",
          },
          {
            menuText: "Trigger another Rapo control execution",
            exampleText: "begin\n\tracs_kpi_pkg.run_rapo_control('PO1_DR_MSC_V', to_date('{control_date:%Y%m%d}', 'yyyymmdd'));\nend;",
          },
        ],
      },
    };
  },
  computed: {
    menuItems() {
      switch (this.label) {
        case "Missmatch criteria (Error config)":
          return this.examples.error_config;
        case "Matching criteria (Rule config)":
          return this.examples.rule_config;
        case "Case config":
          return this.examples.case_config;
        case "Case mapping":
          return this.examples.result_config;
        case "Preparation SQL":
          return this.examples.preparation_sql;
        case "Prerequisite SQL":
          return this.examples.prerequisite_sql;
        case "Completion SQL":
          return this.examples.completion_sql;
        case "Filter":
          return this.examples.source_filter;
        case "Filter (Datasource A)":
          return this.examples.source_filter;
        case "Filter (Datasource B)":
          return this.examples.source_filter;
      }
      return [];
    },
  },
  methods: {
    handleReady(payload) {
      this.view = payload.view;
    },
    setCode(code) {
      this.code = code;
    },
    clearCode() {
      this.code = "";
    },
  },
  watch: {
    code(newValue) {
      this.$emit("update:modelValue", newValue);
    },
    modelValue(newValue) {
      this.code = newValue;
    },
  },
};
</script>

<style>
.cm-editor {
  min-height: 56px;
  max-height: 20em;
  border: 1px solid #bbb;
  border-radius: 0.25em;
  outline: none;
}

.cm-gutters {
  min-height: 56px !important; /* Matches the min-height of .cm-editor */
  border-right: 1px solid #bbb;
  box-sizing: border-box; /* Ensures padding and borders are included in the height calculation */
}

.cm-editor:hover {
  border: 1px solid #666;
}

.cm-editor.cm-focused {
  border: 1px solid #027be3;
  outline: 1px solid #027be3;
}

.cm-activeLine {
  background: transparent !important;
}

.cm-focused .cm-activeLine {
  background: rgba(100, 100, 100, 0.1) !important;
}

.cm-activeLineGutter {
  background: transparent !important;
}

.cm-focused .cm-activeLineGutter {
  background: rgba(100, 100, 100, 0.1) !important;
}
</style>
