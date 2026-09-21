<template>
  <div>
    <span class="row items-center justify-between">
      <label>{{ label }}</label>
      <div>
        <slot name="actions"></slot>
        <q-btn v-if="code && !readonly" class="col-auto" flat size="xs" icon="fas fa-times" @click="clearCode" />
        <q-btn v-if="!readonly" class="col-auto" flat size="sm" label="Example">
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
    <codemirror
      ref="editor"
      class="cm-wrapper"
      :class="{ 'cm-readonly': readonly }"
      v-model="code"
      :indent-with-tab="true"
      :smart-indent="true"
      :tab-size="4"
      :extensions="extensions" />
  </div>
</template>

<script>
import { Codemirror } from "vue-codemirror";
import { EditorState } from "@codemirror/state";
import { sql } from "@codemirror/lang-sql";

export default {
  props: ["modelValue", "label", "readonly", "controlName"],
  emits: ["update:modelValue"],
  components: {
    Codemirror,
  },
  data() {
    return {
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
        // KPI and alarm statements are run by RACS_KPI_PKG with dbms_sql, which takes the first column of
        // the first row. :v_processid is the run, :v_kpi_value the KPI the alarm is evaluated for.
        kpi_sql: [
          {
            menuText: "Count of result records",
            exampleText: "select count(*)\nfrom rapo_rest_<control_name>\nwhere rapo_process_id = :v_processid",
          },
          {
            menuText: "Sum of a result column",
            exampleText: "select coalesce(sum(charge), 0)\nfrom rapo_rest_<control_name>\nwhere rapo_process_id = :v_processid",
          },
          {
            menuText: "Error level of the run",
            exampleText: "select error_level\nfrom rapo_log\nwhere process_id = :v_processid",
          },
        ],
        alarm_sql: [
          {
            menuText: "Single threshold",
            exampleText: "select\ncase\n\twhen :v_kpi_value > 10 then 2\n\telse 0\nend\nfrom dual",
          },
          {
            menuText: "Three alarm levels",
            exampleText: "select\ncase\n\twhen :v_kpi_value > 100 then 3\n\twhen :v_kpi_value > 50 then 2\n\twhen :v_kpi_value > 10 then 1\n\telse 0\nend\nfrom dual",
          },
        ],
      },
    };
  },
  computed: {
    extensions() {
      return [sql(), EditorState.readOnly.of(Boolean(this.readonly))];
    },
    code: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit("update:modelValue", value);
      },
    },
    menuItems() {
      const examplesByLabel = {
        "Mismatch criteria (Error definition)": "error_config",
        "Case mapping": "result_config",
        "Preparation SQL": "preparation_sql",
        "Prerequisite SQL": "prerequisite_sql",
        "Completion SQL": "completion_sql",
        Filter: "source_filter",
        "Filter (Datasource A)": "source_filter",
        "Filter (Datasource B)": "source_filter",
        "KPI SQL statement": "kpi_sql",
        "Alarm SQL statement": "alarm_sql",
      };
      return this.examples[examplesByLabel[this.label]] || [];
    },
  },
  methods: {
    setCode(code) {
      // <control_name> is a placeholder of the example itself. Braces are left alone: rapo interpolates
      // {control_name} and friends in its own statements when the control runs.
      this.code = this.controlName ? code.replaceAll("<control_name>", this.controlName) : code;
    },
    clearCode() {
      this.code = "";
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

/* A read-only editor shows a value that is not the user's to edit, e.g. a KPI type's default statement. */
.cm-readonly .cm-editor {
  background: #f5f5f5;
  color: #757575;
}

.cm-readonly .cm-editor:hover {
  border: 1px solid #bbb;
}

.cm-readonly .cm-cursor {
  display: none !important;
}

.cm-focused .cm-activeLineGutter {
  background: rgba(100, 100, 100, 0.1) !important;
}
</style>
