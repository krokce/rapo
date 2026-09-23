<template>
  <q-page>
    <div v-if="!ready">
      <h2 class="row items-center q-mb-lg">
        <q-skeleton type="QChip" width="90px" height="50px" class="q-mr-md" />
        <q-skeleton type="text" width="420px" height="60px" />
      </h2>
      <editor-skeleton />
    </div>
    <div v-else>
      <h2 class="row q-mb-lg">
        <q-chip
          size="xl"
          text-color="white"
          :class="'bg-' + controlTypeColor(control.control_type)"
          class="text-weight-bold">
          {{ control.control_type }}
        </q-chip>
        &nbsp;
        {{ control.control_name ? control.control_name : "New control" }}
      </h2>

      <q-card>
        <q-tabs
          v-model="tab"
          class="text-white"
          :class="'bg-' + controlTypeColor(control.control_type)"
          active-color="light-blue-1"
          indicator-color="light-blue-1"
          align="justify"
          inline-label
          narrow-indicator
          no-caps>
          <q-tab name="main" label="Main" icon="fas fa-window-maximize" />
          <q-tab name="data" label="Data and logic" icon="fas fa-database" />
          <q-tab name="sql" label="SQL Scripts" icon="fas fa-code" />
          <q-tab v-if="control.control_type !== 'REP' && control.control_type !== 'REC'" name="case" label="Case definition" icon="fas fa-tag" />
          <q-tab name="scheduler" label="Scheduler" icon="fas fa-clock" />
          <q-tab v-if="kpiAvailable" name="kpi" label="KPIs" icon="fas fa-calculator" />
          <q-tab v-if="control.control_id" name="log" label="Run log" icon="fas fa-file-medical-alt" />
        </q-tabs>

        <q-separator />

        <q-form @submit="validateAndSave" @reset="cancel" ref="myForm">
          <q-tab-panels v-model="tab" animated keep-alive>
            <q-tab-panel name="main">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="row q-gutter-md">
                  <q-input
                    class="col"
                    outlined
                    v-model="control.control_name"
                    label="Control name"
                    maxlength="45"
                    @keyup="control && control.control_name && (control.control_name = control.control_name.toUpperCase())" />

                  <q-input class="col" outlined v-model="control.control_alias" label="Control alias" />

                  <q-select
                    v-if="control.control_id"
                    class="col-2"
                    outlined
                    v-model="controlVersion"
                    label="Version"
                    :options="controlVersions"
                    @update:model-value="controlVersionChanged">
                    <template v-slot:prepend>
                      <q-icon
                        name="fas fa-tag"
                        size="sm"
                        @click="showVersionChanges"
                        @click.stop.prevent
                        class="cursor-pointer"
                        :class="{ 'text-deep-orange-4': versionChanges.length }">
                        <q-badge rounded size="xs" v-if="versionChanges.length" color="green" floating>{{ versionChanges.length }}</q-badge>
                        <q-tooltip v-if="versionChanges.length" anchor="top left" self="bottom left" :offset="[0, 5]"> Show changes </q-tooltip>
                      </q-icon>
                    </template>
                    <template v-slot:no-option>
                      <q-item>
                        <q-item-section class="text-grey"> No past versions </q-item-section>
                      </q-item>
                    </template>
                  </q-select>
                </div>

                <div class="row q-gutter-md">
                  <q-input class="col" v-model="control.control_description" label="Control description" maxlength="500" outlined autogrow />
                </div>

                <div class="row q-gutter-md">
                  <q-select
                    class="col"
                    outlined
                    emit-value
                    map-options
                    v-model="control.control_type"
                    :options="controlTypeOptions"
                    label="Control type"
                    @update:model-value="controlTypeChanged" />

                  <q-select
                    class="col"
                    outlined
                    :readonly="control.control_type !== 'REC'"
                    emit-value
                    map-options
                    v-model="control.control_engine"
                    :options="controlEngineOptions"
                    label="Control engine">
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      Reconciliation can run its SQL from Python ('Database SQL') or inside Oracle <br />
                      ('PL-SQL procedure', RAPO_USAGE_RULE). Both produce the same results.
                    </q-tooltip>
                  </q-select>

                  <q-select
                    class="col"
                    outlined
                    emit-value
                    map-options
                    v-model="control.need_prerun_hook"
                    :options="yesNoOptions"
                    label="Pre-run hook">
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      If 'Yes' is selected pre-run hook will be executed before the control is started. <br />
                      function RAPO_PRERUN_CONTROL_HOOK (in_process_id number) return varchar2
                    </q-tooltip>
                  </q-select>

                  <q-select
                    class="col"
                    outlined
                    emit-value
                    map-options
                    v-model="control.need_postrun_hook"
                    :options="yesNoOptions"
                    label="Post-run hook">
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      If 'Yes' is selected post-run hook will be executed after control execution completes. <br />
                      procedure RAPO_POSTRUN_CONTROL_HOOK
                    </q-tooltip>
                  </q-select>
                </div>

                <div class="row q-my-md q-gutter-md">
                  <q-input class="col" v-model.number="control.parallelism" type="number" outlined label="Parallelism" :min="1" :step="1">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-microchip" @click.stop.prevent />
                    </template>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      Execute in parallel mode (oracle /*PARALLEL*/ hint). <br />Recommended maximum is 4.
                    </q-tooltip>
                  </q-input>

                  <q-input class="col" v-model.number="control.instance_limit" type="number" :min="1" :step="1" outlined label="Instance limit">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-stream" @click.stop.prevent />
                    </template>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Number of control instances allowed to run in parallel. </q-tooltip>
                  </q-input>

                  <q-input class="col" v-model.number="control.timeout" type="number" outlined label="Timeout (sec.)">
                    <template v-slot:prepend>
                      <q-icon name="fas fas fa-stopwatch" @click.stop.prevent />
                    </template>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      Stop process if runs longer than defined timeout. <br />Leave empty for no timeout.
                    </q-tooltip>
                  </q-input>

                  <q-select
                    class="col"
                    outlined
                    emit-value
                    map-options
                    v-model="withDeleteionDrop"
                    :options="[
                      { label: 'Yes', value: 'N' },
                      { label: 'No, delete on each run', value: 'deletion' },
                      { label: 'No, drop on each run', value: 'drop' },
                    ]"
                    label="Keep past results"
                    @update:model-value="deletionDropChanged">
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      Results retention policy<br />If 'Yes' is selected define the retention period in the next field.<br />If 'No' is selected the results
                      will be deleted or dropped on each run.
                    </q-tooltip>
                  </q-select>

                  <q-input
                    class="col"
                    v-model.number="control.days_retention"
                    v-if="withDeleteionDrop === 'N'"
                    type="number"
                    outlined
                    label="Retention period (days)">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-trash-alt" @click.stop.prevent />
                    </template>
                  </q-input>
                </div>

                <div class="row q-my-md q-gutter-md">
                  <q-btn label="Save" type="submit" color="primary" />
                  <q-btn label="Cancel" type="reset" color="primary" flat class="q-ml-sm" />
                  <q-btn v-if="control.control_id" label="Recreate schema" color="red" flat class="q-ml-auto" @click="recreateSchema(control)" />
                </div>
              </div>
            </q-tab-panel>

            <q-tab-panel name="data">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="row q-gutter-md" v-if="control.control_type === 'ANL' || control.control_type === 'REP'">
                  <q-select
                    class="col"
                    outlined
                    v-model="control.source_name"
                    use-input
                    hide-selected
                    fill-input
                    input-debounce="0"
                    label="Datasource"
                    :options="datasourceListOptions"
                    @filter="filterDatasourceList">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-table" @click.stop.prevent />
                    </template>
                    <template v-slot:no-option>
                      <q-item>
                        <q-item-section class="text-grey"> No datasources found </q-item-section>
                      </q-item>
                    </template>
                  </q-select>

                  <q-select
                    v-if="control.control_type === 'ANL' || control.control_type === 'REP'"
                    class="col-2"
                    outlined
                    v-model="control.source_date_field"
                    label="Date column"
                    :options="datasourceDateColumns"
                    clearable
                    behavior="menu">
                    <template v-slot:prepend>
                      <q-icon name="far fa-calendar-alt" @click.stop.prevent />
                    </template>
                  </q-select>

                  <q-input class="col-2" outlined v-model="control.source_type_a" label="System" maxlength="90" />
                </div>

                <div class="row q-gutter-md" v-if="control.control_type === 'REC' || control.control_type === 'CMP'">
                  <q-select
                    class="col"
                    outlined
                    v-model="control.source_name_a"
                    use-input
                    hide-selected
                    fill-input
                    input-debounce="0"
                    label="Datasource A"
                    :options="datasourceListOptions"
                    @filter="filterDatasourceList">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-table" @click.stop.prevent />
                    </template>
                    <template v-slot:no-option>
                      <q-item>
                        <q-item-section class="text-grey"> No datasources found </q-item-section>
                      </q-item>
                    </template>
                  </q-select>

                  <q-select
                    v-if="control.control_type === 'REC'"
                    class="col-1"
                    outlined
                    v-model="control.source_key_field_a"
                    input-debounce="0"
                    label="Key field A"
                    :options="[...new Set([...(datasourceAColumns ? datasourceAColumns : []), 'TAG'])]">
                  </q-select>

                  <q-select
                    v-if="control.control_type === 'CMP'"
                    class="col-2"
                    outlined
                    clearable
                    v-model="control.source_date_field_a"
                    label="Date column A"
                    :options="datasourceADateColumns"
                    behavior="menu">
                    <template v-slot:prepend>
                      <q-icon name="far fa-calendar-alt" @click.stop.prevent />
                    </template>
                  </q-select>

                  <q-input class="col-1" outlined v-model="control.source_type_a" label="System A" maxlength="90" />

                  <q-select
                    class="col"
                    outlined
                    v-model="control.source_name_b"
                    use-input
                    hide-selected
                    fill-input
                    input-debounce="0"
                    label="Datasource B"
                    :options="datasourceListOptions"
                    @filter="filterDatasourceList">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-table" @click.stop.prevent />
                    </template>
                    <template v-slot:no-option>
                      <q-item>
                        <q-item-section class="text-grey"> No datasources found </q-item-section>
                      </q-item>
                    </template>
                  </q-select>

                  <q-select
                    v-if="control.control_type === 'REC'"
                    class="col-1"
                    outlined
                    v-model="control.source_key_field_b"
                    input-debounce="0"
                    label="Key field B"
                    :options="[...new Set([...(datasourceBColumns ? datasourceBColumns : []), 'TAG'])]">
                  </q-select>

                  <q-select
                    v-if="control.control_type === 'CMP'"
                    class="col-2"
                    outlined
                    clearable
                    v-model="control.source_date_field_b"
                    label="Date column B"
                    :options="datasourceBDateColumns"
                    behavior="menu">
                    <template v-slot:prepend>
                      <q-icon name="far fa-calendar-alt" @click.stop.prevent />
                    </template>
                  </q-select>

                  <q-input class="col-1" outlined v-model="control.source_type_b" label="System B" maxlength="90" />
                </div>

                <div class="row q-gutter-md">
                  <q-select
                    v-if="control.control_type === 'ANL' || control.control_type === 'REP'"
                    class="col"
                    outlined
                    clearable
                    v-model="control.output_table_columns"
                    multiple
                    :options="datasourceColumns"
                    use-chips
                    stack-label
                    label="Select output (leave empty for all columns)">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-columns" @click.stop.prevent="populateColumns()">
                        <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Get all columns </q-tooltip>
                      </q-icon>
                    </template>
                  </q-select>

                  <q-input
                    v-if="control.control_type === 'ANL' || control.control_type === 'REP'"
                    class="col-2"
                    v-model.number="control.output_limit"
                    type="number"
                    outlined
                    label="Output limit">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-list-ol" @click.stop.prevent />
                    </template>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      Limit the number of records in the output table. <br />Leave empty for no limit.
                    </q-tooltip>
                  </q-input>

                  <div v-if="control.control_type === 'CMP'" class="col">
                    <comparison-output-table-box
                      class="col"
                      v-model="cmpOutputTable"
                      :datasource-a-columns="datasourceAColumns"
                      :datasource-b-columns="datasourceBColumns">
                    </comparison-output-table-box>
                  </div>

                  <q-input
                    v-if="control.control_type === 'CMP'"
                    class="col-2"
                    v-model.number="control.output_limit"
                    type="number"
                    outlined
                    label="Output limit">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-list-ol" @click.stop.prevent />
                    </template>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      Limit the number of records in the output table. <br />Leave empty for no limit.
                    </q-tooltip>
                  </q-input>

                  <q-select
                    v-if="control.control_type === 'REC'"
                    class="col"
                    outlined
                    clearable
                    v-model="control.output_table_a_columns"
                    multiple
                    :options="datasourceAColumns"
                    use-chips
                    stack-label
                    label="Select output A-side (leave empty for all columns)">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-columns" @click.stop.prevent="populateColumns('A')">
                        <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Get all columns </q-tooltip>
                      </q-icon>
                    </template>
                  </q-select>

                  <q-select
                    v-if="control.control_type === 'REC'"
                    class="col"
                    outlined
                    clearable
                    v-model="control.output_table_b_columns"
                    multiple
                    :options="datasourceBColumns"
                    use-chips
                    stack-label
                    label="Select output B-side (leave empty for all columns)">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-columns" @click.stop.prevent="populateColumns('B')">
                        <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Get all columns </q-tooltip>
                      </q-icon>
                    </template>
                  </q-select>
                </div>

                <div class="row q-my-sm q-gutter-md">
                  <div class="col" v-if="control.control_type === 'ANL' || control.control_type === 'REP'">
                    <code-box label="Filter" v-model="control.source_filter" :columns="datasourceColumns"> </code-box>
                  </div>
                  <div class="col" v-if="control.control_type === 'REC' || control.control_type === 'CMP'">
                    <code-box label="Filter (Datasource A)" v-model="control.source_filter_a" :columns="datasourceAColumns"> </code-box>
                  </div>
                  <div class="col" v-if="control.control_type === 'REC' || control.control_type === 'CMP'">
                    <code-box label="Filter (Datasource B)" v-model="control.source_filter_b" :columns="datasourceBColumns"> </code-box>
                  </div>
                </div>

                <div class="row q-my-xs q-gutter-md" v-if="control.control_type == 'ANL'">
                  <div class="col">
                    <code-box label="Mismatch criteria (Error definition)" v-model="control.error_definition" :columns="datasourceColumns"> </code-box>
                  </div>
                </div>

                <div class="row q-my-xs q-gutter-md" v-if="control.control_type == 'CMP'">
                  <div class="col">
                    <comparison-criteria-box
                      class="col"
                      title="Match criteria"
                      v-model="ruleConfigObject"
                      :datasource-a-columns="datasourceAColumns"
                      :datasource-b-columns="datasourceBColumns" />
                  </div>
                  <div class="col">
                    <comparison-criteria-box
                      class="col"
                      title="Mismatch criteria"
                      icon="fas fa-not-equal"
                      v-model="ruleErrorObject"
                      :datasource-a-columns="datasourceAColumns"
                      :datasource-b-columns="datasourceBColumns" />
                  </div>
                </div>

                <div class="col q-my-lg q-gutter-y-md" v-if="control.control_type === 'REC'">
                  <q-card class="q-pa-sm" flat bordered>
                    <q-item-section class="q-ma-xs">
                      <q-item-label>Time dimension</q-item-label>
                    </q-item-section>

                    <q-card-section class="q-gutter-xs">
                      <div class="row q-gutter-xs items-center">
                        <q-select
                          class="col-2"
                          outlined
                          v-model="control.source_date_field_a"
                          label="Date column A"
                          :options="datasourceADateColumns"
                          behavior="menu">
                          <template v-slot:prepend>
                            <q-icon name="far fa-calendar-alt" @click.stop.prevent />
                          </template>
                        </q-select>

                        <q-icon class="q-py-md" name="fas fa-equals" size="20px" color="blue-grey-3" />

                        <q-select
                          class="col-2"
                          outlined
                          v-model="control.source_date_field_b"
                          label="Date column B"
                          :options="datasourceBDateColumns"
                          behavior="menu">
                          <template v-slot:prepend>
                            <q-icon name="far fa-calendar-alt" @click.stop.prevent />
                          </template>
                        </q-select>

                        <q-icon
                          v-if="control.source_date_field_a && control.source_date_field_b"
                          class="q-py-md"
                          name="fas fa-circle"
                          size="15px"
                          color="blue-grey-3" />

                        <q-input
                          v-if="control.source_date_field_a && control.source_date_field_b"
                          outlined
                          class="col"
                          v-model.number="ruleConfigObject.time_tolerance_from"
                          type="number"
                          label="Time tolerance from"
                          @update:model-value="ReconciliationTimeFromToleranceChanged">
                          <template v-slot:prepend>
                            <q-icon name="fas fa-long-arrow-alt-left" @click.stop.prevent />
                          </template>
                          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                            Lower timestamp tolerance value in seconds (match if A minus B timestamp is greater than this value in seconds)
                          </q-tooltip>
                        </q-input>

                        <q-input
                          v-if="control.source_date_field_a && control.source_date_field_b"
                          outlined
                          class="col"
                          v-model.number="ruleConfigObject.time_tolerance_to"
                          type="number"
                          label="Time tolerance to"
                          @update:model-value="ReconciliationTimeToToleranceChanged">
                          <template v-slot:prepend>
                            <q-icon name="fas fa-long-arrow-alt-right" @click.stop.prevent />
                          </template>
                          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                            Upper timestamp tolerance value in seconds (match if A minus B timestamp is lower than this value in seconds)
                          </q-tooltip>
                        </q-input>

                        <q-icon
                          v-if="control.source_date_field_a && control.source_date_field_b"
                          class="q-py-md"
                          name="fas fa-circle"
                          size="15px"
                          color="blue-grey-3" />

                        <q-input
                          v-if="control.source_date_field_a && control.source_date_field_b"
                          outlined
                          class="col"
                          v-model.number="ruleConfigObject.time_shift_from"
                          type="number"
                          label="Time shift from"
                          @update:model-value="ReconciliationTimeShiftFromChanged">
                          <template v-slot:prepend>
                            <q-icon name="far fa-clock" @click.stop.prevent />
                          </template>
                          <q-tooltip anchor="top right" self="bottom right" :offset="[0, 5]">
                            Lower timeshift tolerance value in seconds <br />
                            (if A minus B is between this value and "Time tolerance from" - output as mismatch)
                          </q-tooltip>
                        </q-input>

                        <q-input
                          v-if="control.source_date_field_a && control.source_date_field_b"
                          outlined
                          class="col"
                          v-model.number="ruleConfigObject.time_shift_to"
                          type="number"
                          label="Time shift to"
                          @update:model-value="ReconciliationTimeShiftToChanged">
                          <template v-slot:prepend>
                            <q-icon name="far fa-clock" @click.stop.prevent />
                          </template>
                          <q-tooltip anchor="top right" self="bottom right" :offset="[0, 5]">
                            Upper timeshift tolerance value in seconds <br />
                            (if A minus B is between "Time tolerance to" and this value - output as mismatch)
                          </q-tooltip>
                        </q-input>
                      </div>
                    </q-card-section>
                  </q-card>

                  <reconciliation-match-criteria-box
                    class="col"
                    v-model="ruleConfigObject"
                    :datasource-a-columns="datasourceAColumns"
                    :datasource-b-columns="datasourceBColumns">
                  </reconciliation-match-criteria-box>

                  <reconciliation-mis-match-criteria-box
                    class="col"
                    v-model="ruleConfigObject"
                    :datasource-a-columns="datasourceANumColumns"
                    :datasource-b-columns="datasourceBNumColumns">
                  </reconciliation-mis-match-criteria-box>

                  <reconciliation-discrepancy-checkboxes class="col" :control="control" v-model="ruleConfigObject">
                  </reconciliation-discrepancy-checkboxes>
                  <br />
                </div>

                <div class="row q-my-md q-gutter-md">
                  <q-btn label="Save" type="submit" color="primary" />
                  <q-btn label="Cancel" type="reset" color="primary" flat class="q-ml-sm" />
                </div>
              </div>
            </q-tab-panel>

            <q-tab-panel name="sql">
              <div class="q-ma-lg q-gutter-y-lg">
                <div class="row q-gutter-md">
                  <div class="col">
                    <code-box label="Preparation SQL" :template-vars="true" :tables="ruleDatasourceTables" v-model="control.preparation_sql"></code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[-120, -20]">
                      Preparation SQL is executed before the control is started. It can be used to prepare the data for the control. See the enclosed examples.
                    </q-tooltip>
                  </div>
                </div>

                <div class="row q-gutter-md">
                  <div class="col">
                    <code-box label="Prerequisite SQL" :template-vars="true" :tables="ruleDatasourceTables" v-model="control.prerequisite_sql"> </code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[-120, -20]">
                      Prerequisite SQL is executed before the control is started. If the number returned is 0 the control will be terminated. See the enclosed
                      positive and negative examples.
                    </q-tooltip>
                  </div>
                </div>

                <div class="row q-gutter-md">
                  <div class="col">
                    <code-box label="Completion SQL" :template-vars="true" :tables="ruleDatasourceTables" v-model="control.completion_sql"> </code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[-120, -20]">
                      Completion SQL is executed after the control is finished. It can be used to clean-up data, log results or execute chain of controls. See
                      the enclosed examples.
                    </q-tooltip>
                  </div>
                </div>

                <div class="row q-my-md q-gutter-md">
                  <q-btn label="Save" type="submit" color="primary" />
                  <q-btn label="Cancel" type="reset" color="primary" flat class="q-ml-sm" />
                </div>
              </div>
            </q-tab-panel>

            <q-tab-panel name="case">
              <div class="q-ma-lg">
                <div class="column q-gutter-y-xl">
                  <div class="col">
                    <case-config-box class="col" v-model="caseConfigObject"> </case-config-box>
                  </div>
                  <div class="col">
                    <code-box label="Case mapping" v-model="control.case_definition"> </code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      Use simple SQL case structure to define which discrepancies will be mapped to which Case IDs defined above. See the enclosed example.
                    </q-tooltip>
                  </div>
                </div>

                <div class="row q-my-md q-gutter-md">
                  <q-btn label="Save" type="submit" color="primary" />
                  <q-btn label="Cancel" type="reset" color="primary" flat class="q-ml-sm" />
                </div>
              </div>
            </q-tab-panel>

            <q-tab-panel name="scheduler">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="row q-gutter-md">
                  <q-select
                    class="col-2"
                    outlined
                    emit-value
                    map-options
                    v-model="control.status"
                    :options="[
                      { label: 'Active', value: 'Y' },
                      { label: 'Inactive', value: 'N' },
                    ]"
                    label="Scheduler status" />

                  <schedule-edit-box class="col" v-model="scheduleObject"></schedule-edit-box>
                </div>
                <div class="row q-gutter-md">
                  <q-input outlined class="col-2" v-model.number="control.period_back" type="number" label="Periods back">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-history" @click.stop.prevent />
                    </template>
                  </q-input>

                  <q-input class="col-2" v-model.number="control.period_number" type="number" outlined label="Number of periods">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-calendar-day" @click.stop.prevent />
                    </template>
                  </q-input>

                  <q-select
                    class="col-2"
                    outlined
                    emit-value
                    map-options
                    v-model="control.period_type"
                    :options="periodTypeOptions"
                    label="Period type" />
                </div>

                <div v-if="scheduleType !== 'C'" class="row q-gutter-md">
                  <iteration-config-box class="col" v-model="iterationConfigObject" :pb="control.period_back"> </iteration-config-box>
                </div>

                <div class="row q-gutter-md">
                  <q-btn label="Save" type="submit" color="primary" />
                  <q-btn label="Cancel" type="reset" color="primary" flat class="q-ml-sm" />
                </div>
              </div>
            </q-tab-panel>
            <q-tab-panel name="kpi">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="row q-gutter-md">
                  <kpi-config-box class="col" v-model="kpiConfigObject" :control-name="control.control_name" :control-type="control.control_type">
                  </kpi-config-box>
                </div>

                <div class="row q-gutter-md">
                  <q-btn label="Save" type="submit" color="primary" />
                  <q-btn label="Cancel" type="reset" color="primary" flat class="q-ml-sm" />
                </div>
              </div>
            </q-tab-panel>
            <q-tab-panel name="log">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="row q-my-lg">
                  <q-input
                    class="col-1"
                    v-model.number="log_days_back"
                    type="number"
                    outlined
                    label="Days back"
                    :min="1"
                    :max="365"
                    :step="1"
                    @update:model-value="updateLogDaysBack">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-history" @click.stop.prevent />
                    </template>
                  </q-input>
                </div>
                <q-markup-table flat dense>
                  <thead>
                    <tr class="bg-blue-grey-2">
                      <th class="text-left">#</th>
                      <th class="text-left">Added</th>
                      <th class="text-left">Start</th>
                      <th class="text-left">End</th>
                      <th class="text-left">Runtime</th>
                      <th class="text-left">PID</th>
                      <th class="text-left">Run from</th>
                      <th class="text-left">Run to</th>
                      <th class="text-right">Fetched A</th>
                      <th class="text-right">Fetched B</th>
                      <th class="text-right">Discr. A</th>
                      <th class="text-right">Discr. B</th>
                      <th class="text-right">Err. lvl A [%]</th>
                      <th class="text-right">Err. lvl B [%]</th>
                      <th class="text-right">PV</th>
                      <th class="text-left">Status</th>
                      <th class="text-left"></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(log, index) in controlLogs" :key="log.process_id" :class="{ 'new-day-separator': newDayLogRows.has(index) }">
                      <td class="text-left">{{ index + 1 }}. &nbsp;</td>
                      <td v-for="field in ['added', 'start_date', 'end_date']" :key="field" class="text-left">
                        <div class="text-blue-grey-7">
                          <strong>{{ toDateString(log[field]) }}</strong>
                          <small class="text-grey-7 q-px-sm">{{ toTimeString(log[field]) }}</small>
                        </div>
                      </td>
                      <td class="text-right">
                        {{ log.end_date && log.start_date ? round((new Date(log.end_date) - new Date(log.start_date)) / 60000, 1) : "0" }} min
                      </td>
                      <td class="text-left text-weight-bold text-blue-grey-7">{{ log.process_id }}</td>
                      <td class="text-left">{{ toDateString(log.date_from) }}</td>
                      <td class="text-left">{{ toDateString(log.date_to) }}</td>
                      <td class="text-right">
                        <span v-if="logSum(log, 'fetched_number') > 0 && control.control_type === 'REP'" class="cursor-pointer text-red" @click="copyResultsSql(logRun(log), 'A')">
                          {{ formatNumber(logSum(log, "fetched_number")) }}
                        </span>
                        <span v-else class="cursor-pointer" @click="copyFetchSql(log, singleSource ? 'T' : 'A')">
                          {{ formatNumber(logSum(log, "fetched_number")) }}
                        </span>
                      </td>
                      <td class="text-right">
                        <span class="cursor-pointer" @click="copyFetchSql(log, singleSource ? 'T' : 'B')">{{ formatNumber(log.fetched_number_b) }}</span>
                      </td>
                      <td class="text-right">
                        <span :class="{ 'cursor-pointer text-red': logSum(log, 'error_number') > 0 }" @click="logSum(log, 'error_number') > 0 && copyResultsSql(logRun(log), 'A')">
                          {{ formatNumber(logSum(log, "error_number")) }}
                        </span>
                      </td>
                      <td class="text-right">
                        <span :class="{ 'cursor-pointer text-red': log.error_number_b > 0 }" @click="log.error_number_b > 0 && copyResultsSql(logRun(log), 'B')">
                          {{ formatNumber(log.error_number_b) }}
                        </span>
                      </td>
                      <td class="text-right">
                        <span :class="{ 'cursor-pointer text-red': logSum(log, 'error_level') > 0 }" @click="logSum(log, 'error_level') > 0 && copyResultsSql(logRun(log), 'A')">
                          {{ formatNumber(logSum(log, "error_level"), 2) }}%
                        </span>
                      </td>
                      <td class="text-right">
                        <span :class="{ 'cursor-pointer text-red': log.error_level_b > 0 }" @click="log.error_level_b > 0 && copyResultsSql(logRun(log), 'B')">
                          {{ formatNumber(log.error_level_b, 2) }}%
                        </span>
                      </td>
                      <td class="text-right">
                        <q-icon v-if="log.prerequisite_value == 0" class="cursor-pointer text-red" name="fas fa-stop">
                          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Prerequisite SQL value is 0 </q-tooltip>
                        </q-icon>
                        <q-icon v-if="log.prerequisite_value" class="cursor-pointer text-green" name="fas fa-play">
                          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Prerequisite SQL value is {{ log.prerequisite_value }} </q-tooltip>
                        </q-icon>
                      </td>
                      <td class="text-left">
                        <q-chip>
                          <q-avatar :icon="runStatus(log.status).icon" :color="runStatus(log.status).color" text-color="white" />
                          {{ runStatus(log.status).label }}
                        </q-chip>
                      </td>
                      <td class="text-left" style="width: 50px">
                        <q-btn size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v">
                          <q-menu>
                            <q-list dense class="text-no-wrap">
                              <q-item dense clickable @click="reRun(logRun(log), refreshLogs)" v-close-popup>
                                <q-item-section> Re-run </q-item-section>
                              </q-item>
                              <q-separator />
                              <q-item v-if="activeRunStatuses.includes(log.status)" dense clickable @click="cancelRun(logRun(log), refreshLogs)" v-close-popup>
                                <q-item-section> Cancel run </q-item-section>
                              </q-item>
                              <q-item v-if="log.status != 'X'" dense clickable @click="revokeRun(logRun(log), refreshLogs)" v-close-popup>
                                <q-item-section> Revoke run </q-item-section>
                              </q-item>
                              <q-item dense clickable @click="$refs.runLogDialog.open({ process_id: log.process_id, control_name: control.control_name })" v-close-popup>
                                <q-item-section> Show full log </q-item-section>
                              </q-item>
                              <q-item dense clickable @click="dropTemporaryTables(logRun(log))" v-close-popup>
                                <q-item-section> Drop temporary tables </q-item-section>
                              </q-item>
                            </q-list>
                          </q-menu>
                        </q-btn>
                      </td>
                    </tr>
                  </tbody>
                </q-markup-table>

                <div class="row q-my-md q-gutter-md">
                  <q-btn label="Save" type="submit" color="primary" />
                  <q-btn label="Cancel" type="reset" color="primary" flat class="q-ml-sm" />
                </div>
              </div>
            </q-tab-panel>
          </q-tab-panels>
        </q-form>
      </q-card>
    </div>

    <run-log-dialog ref="runLogDialog" />
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import { api, notifyError } from "../api";
import { ACTIVE_RUN_STATUSES, CONTROL_ENGINE_OPTIONS, CONTROL_TYPE_OPTIONS, PERIOD_TYPE_OPTIONS, YES_NO_OPTIONS, controlTypeColor, runStatus } from "../constants";
import { cancelRun, copyResultsSql, copySql, dropTemporaryTables, reRun, revokeRun, showText } from "../runActions";
import { liveRefetch } from "../socket";
import CodeBox from "./CodeBox.vue";
import EditorSkeleton from "./EditorSkeleton.vue";
import RunLogDialog from "./RunLogDialog.vue";
import ScheduleEditBox from "./ScheduleEditBox.vue";
import ReconciliationDiscrepancyCheckboxes from "./ReconciliationDiscrepancyCheckboxes.vue";
import ReconciliationMatchCriteriaBox from "./ReconciliationMatchCriteriaBox.vue";
import ReconciliationMisMatchCriteriaBox from "./ReconciliationMisMatchCriteriaBox.vue";
import CaseConfigBox from "./CaseConfigBox.vue";
import IterationConfigBox from "./IterationConfigBox.vue";
import KpiConfigBox from "./KpiConfigBox.vue";
import ComparisonCriteriaBox from "./ComparisonCriteriaBox.vue";
import ComparisonOutputTableBox from "./ComparisonOutputTableBox.vue";
import { formatNumber, round, toDateString, toDateTimeString, toTimeString } from "../utils/format";
import { defaultSchedule, parseSchedule, scheduleType, serializeSchedule } from "../utils/schedule";

export default {
  components: {
    CodeBox,
    EditorSkeleton,
    RunLogDialog,
    ScheduleEditBox,
    ReconciliationDiscrepancyCheckboxes,
    ReconciliationMatchCriteriaBox,
    ReconciliationMisMatchCriteriaBox,
    CaseConfigBox,
    IterationConfigBox,
    KpiConfigBox,
    ComparisonCriteriaBox,
    ComparisonOutputTableBox,
  },
  props: {
    controlId: {
      type: String,
      default: "new",
    },
  },
  data() {
    return {
      tab: "main",
      // False until the control (or a new one) is set up, so the editor never shows an empty form first.
      ready: false,
      control: {},
      controlVersions: [],
      controlVersion: null,
      log_days_back: 7,
      datasourceColumns: null,
      datasourceDateColumns: null,
      datasourceAColumns: null,
      datasourceADateColumns: null,
      datasourceANumColumns: null,
      datasourceBColumns: null,
      datasourceBDateColumns: null,
      datasourceBNumColumns: null,
      datasourceList: null,
      datasourceListOptions: null,
      withDeleteionDrop: "N",
      scheduleObject: defaultSchedule(),
      ruleConfigObject: {},
      cmpOutputTable: [],
      ruleErrorObject: [],
      caseConfigObject: [],
      iterationConfigObject: [],
      kpiConfigObject: [],
      controlLogs: [],
      versionChanges: [],
      saving: false,
      // True while a control is being loaded, so the datasource watchers don't reset its saved fields.
      initializing: false,
      loadedUpdatedDate: null,
      controlTypeOptions: CONTROL_TYPE_OPTIONS,
      yesNoOptions: YES_NO_OPTIONS,
      periodTypeOptions: PERIOD_TYPE_OPTIONS,
      activeRunStatuses: ACTIVE_RUN_STATUSES,
    };
  },
  created() {
    // Pending/finished get-datasource-columns requests by datasource name (see getDatasourceColumns).
    this.columnRequests = {};
  },
  computed: {
    ...mapGetters(["controlCatalogueById"]),
    ...mapState(["kpiTypes"]),
    // The PL-SQL engine implements reconciliation only, so it is offered there.
    controlEngineOptions() {
      return CONTROL_ENGINE_OPTIONS.filter((option) => option.value !== "PL" || this.control.control_type === "REC");
    },
    // The KPI tables belong to the RACS deployment and are optional. No types, no KPIs tab.
    kpiAvailable() {
      return this.kpiTypes.length > 0;
    },
    scheduleType() {
      return scheduleType(this.scheduleObject);
    },
    // ANL and REP read one datasource (source_name), REC and CMP read A and B.
    singleSource() {
      return this.control.control_type === "ANL" || this.control.control_type === "REP";
    },
    // The control's own configured datasource(s) and their columns, for the Preparation/Prerequisite/Completion
    // SQL boxes' autocomplete: one for ANL/REP, A and B for REC/CMP.
    ruleDatasourceTables() {
      const tables = {};
      if (this.singleSource) {
        if (this.control.source_name) tables[this.control.source_name] = this.datasourceColumns || [];
      } else {
        if (this.control.source_name_a) tables[this.control.source_name_a] = this.datasourceAColumns || [];
        if (this.control.source_name_b) tables[this.control.source_name_b] = this.datasourceBColumns || [];
      }
      return tables;
    },
    // Indexes of run log rows added on another day than the previous row, drawn with a separator line.
    newDayLogRows() {
      const logs = this.controlLogs;
      return new Set(logs.map((log, index) => index).filter((index) => index > 0 && toDateString(logs[index - 1].added) !== toDateString(logs[index].added)));
    },
  },
  methods: {
    ...mapActions(["updateControlCatalogue", "updateKpiTypes"]),
    updateLogDaysBack() {
      return this.refreshLogs();
    },
    controlTypeColor,
    formatNumber,
    round,
    runStatus,
    toDateString,
    toTimeString,
    reRun,
    cancelRun,
    revokeRun,
    dropTemporaryTables,
    copyResultsSql,
    showVersionChanges() {
      if (this.versionChanges.length) {
        showText(this.control.control_name + " | " + this.controlVersion.label, this.formattedJSON(this.versionChanges));
      }
    },
    formattedJSON(control) {
      return JSON.stringify(control, null, 2).replace(/\\"/g, "'");
    },
    filterDatasourceList(val, update) {
      update(() => {
        const needle = val.toLowerCase();
        this.datasourceListOptions = (this.datasourceList || []).filter((v) => v.toLowerCase().includes(needle));
      });
    },
    async loadKpiTypes() {
      try {
        await this.updateKpiTypes();
      } catch (error) {
        notifyError("KPI types were not loaded.", error);
      }
    },
    // racs_kpi_config rows of one control, by name. Not versioned, so a version switch reloads the same rows.
    async loadControlKpis(controlName) {
      this.kpiConfigObject = [];
      if (!this.kpiAvailable || !controlName) {
        return;
      }
      try {
        this.kpiConfigObject = await api("get-control-kpis", { params: { control_name: controlName }, loadingBar: false });
      } catch (error) {
        notifyError("KPI configuration was not loaded.", error);
      }
    },
    async getDatasources() {
      try {
        this.datasourceList = await api("get-datasources");
      } catch (error) {
        notifyError("Failed to load datasources.", error);
      }
    },
    // Column names of a datasource, optionally only those of one kind ("numeric", "string", "date").
    // Each datasource's columns are fetched once per page and shared by all kinds.
    async getDatasourceColumns(datasource_name, which) {
      if (!datasource_name) {
        return [];
      }
      if (!this.columnRequests[datasource_name]) {
        this.columnRequests[datasource_name] = api("get-datasource-columns", { params: { datasource_name } }).catch((error) => {
          delete this.columnRequests[datasource_name];
          notifyError("Failed to load columns of " + datasource_name + ".", error);
          return [];
        });
      }
      const columns = await this.columnRequests[datasource_name];
      const kinds = {
        numeric: (type) => ["NUMBER", "FLOAT", "DOUBLE", "DECIMAL", "INTEGER"].some((t) => type.includes(t)),
        string: (type) => type.includes("CHAR"),
        date: (type) => type.includes("TIMESTAMP") || type === "DATE",
      };
      return columns.filter((column) => !kinds[which] || kinds[which](column.data_type.toUpperCase())).map((column) => column.column_name);
    },
    populateColumns(side) {
      if (side === "A") {
        this.control.output_table_a_columns = this.datasourceAColumns;
      } else if (side === "B") {
        this.control.output_table_b_columns = this.datasourceBColumns;
      } else {
        this.control.output_table_columns = this.datasourceColumns;
      }
    },
    // Unset options (correlation_limit, fuzzy_optimization, ...) fall back to the rapo.ini defaults.
    defaultReconciliationRuleConfig() {
      return {
        need_issues_a: true,
        need_issues_b: true,
        need_recons_a: false,
        need_recons_b: false,
        output_limit_a: null,
        output_limit_b: null,
        allow_duplicates: false,
        time_shift_from: 0,
        time_shift_to: 0,
        time_tolerance_from: 0,
        time_tolerance_to: 0,
        correlation_config: [],
        discrepancy_config: [],
      };
    },
    // CMP output columns: drop unset fields and upper-case column names.
    normalizeOutputColumns(columns) {
      return (columns || []).map((column) =>
        Object.fromEntries(Object.entries(column).filter(([, value]) => value != null).map(([key, value]) => [key, String(value).toUpperCase()]))
      );
    },
    controlTypeChanged(newValue) {
      // The PL-SQL engine only implements reconciliation.
      if (newValue !== "REC" && this.control.control_engine === "PL") {
        this.control.control_engine = "DB";
      }
      this.control.source_name = null;
      this.control.source_name_a = null;
      this.control.source_name_b = null;
      this.control.source_date_field = null;
      this.control.source_date_field_a = null;
      this.control.source_key_field_a = null;
      this.control.source_date_field_b = null;
      this.control.source_key_field_b = null;
      this.control.rule_config = null;
      this.control.error_definition = null;
      this.control.source_filter = null;
      this.control.source_filter_a = null;
      this.control.source_filter_b = null;
      this.control.case_config = null;
      this.control.timeout = 3600;
      this.control.result_config = null;
      this.control.output_table = null;
      this.control.output_table_a = null;
      this.control.output_table_b = null;
      this.control.output_table_columns = [];
      this.control.output_table_a_columns = [];
      this.control.output_table_b_columns = [];
      this.control.output_limit = null;

      if (newValue === "REC") {
        this.ruleConfigObject = this.defaultReconciliationRuleConfig();

        this.control.source_key_field_a = "TAG";
        this.control.source_key_field_b = "TAG";
      } else if (newValue === "CMP") {
        this.ruleConfigObject = [];
        this.ruleErrorObject = [];
      } else {
        this.ruleConfigObject = null;
      }
    },
    async getControlVersions(controlId) {
      try {
        const versions = await api("get-control-versions", { params: { control_id: controlId } });
        const label = (version) => "v." + toDateTimeString(version.updated_date ? version.updated_date : version.created_date);
        versions.forEach((version) => (version.label = label(version)));
        this.control.label = label(this.control);
        this.controlVersions = [this.control, ...versions];
        this.controlVersion = this.control;
      } catch (error) {
        notifyError("Failed to load control versions.", error);
      }
    },
    async getControlLogs(controlName, numberDays) {
      try {
        this.controlLogs = await api("read-control-logs", { params: { control_name: controlName, days: numberDays } });
      } catch (error) {
        notifyError("Failed to load run log.", error);
      }
    },
    refreshLogs() {
      return this.getControlLogs(this.control.control_name, this.log_days_back);
    },
    // Log rows lack the control's name and type, which the run actions need.
    logRun(log) {
      return { ...log, control_name: this.control.control_name, control_type: this.control.control_type };
    },
    // Single-source controls log counts without a side suffix (fetched_number), A/B controls with one.
    logSum(log, field) {
      return Number(log[field + "_a"]) + Number(log[field]);
    },
    ReconciliationTimeFromToleranceChanged() {
      if (!isNaN(Number(this.ruleConfigObject.time_tolerance_from))) {
        if (Number(this.ruleConfigObject.time_tolerance_from) < Number(this.ruleConfigObject.time_shift_from)) {
          this.ruleConfigObject.time_shift_from = this.ruleConfigObject.time_tolerance_from;
        }
        if (Number(this.ruleConfigObject.time_tolerance_from) > Number(this.ruleConfigObject.time_tolerance_to)) {
          this.ruleConfigObject.time_tolerance_to = this.ruleConfigObject.time_tolerance_from;
        }
      }
    },
    ReconciliationTimeToToleranceChanged() {
      if (!isNaN(Number(this.ruleConfigObject.time_tolerance_to))) {
        if (Number(this.ruleConfigObject.time_tolerance_to) > Number(this.ruleConfigObject.time_shift_to)) {
          this.ruleConfigObject.time_shift_to = this.ruleConfigObject.time_tolerance_to;
        }
        if (Number(this.ruleConfigObject.time_tolerance_from) > Number(this.ruleConfigObject.time_tolerance_to)) {
          this.ruleConfigObject.time_tolerance_from = this.ruleConfigObject.time_tolerance_to;
        }
      }
    },
    ReconciliationTimeShiftFromChanged() {
      if (!isNaN(Number(this.ruleConfigObject.time_shift_from))) {
        if (Number(this.ruleConfigObject.time_shift_from) > Number(this.ruleConfigObject.time_tolerance_from)) {
          this.ruleConfigObject.time_tolerance_from = this.ruleConfigObject.time_shift_from;
        }
        if (Number(this.ruleConfigObject.time_shift_from) > Number(this.ruleConfigObject.time_shift_to)) {
          this.ruleConfigObject.time_shift_to = this.ruleConfigObject.time_shift_from;
        }
      }
    },
    ReconciliationTimeShiftToChanged() {
      if (!isNaN(Number(this.ruleConfigObject.time_shift_to))) {
        if (Number(this.ruleConfigObject.time_shift_to) < Number(this.ruleConfigObject.time_tolerance_to)) {
          this.ruleConfigObject.time_tolerance_to = this.ruleConfigObject.time_shift_to;
        }
        if (Number(this.ruleConfigObject.time_shift_from) > Number(this.ruleConfigObject.time_shift_to)) {
          this.ruleConfigObject.time_shift_from = this.ruleConfigObject.time_shift_to;
        }
      }
    },
    initializeControl() {
      try {
        if (this.control.control_type === "ANL" || this.control.control_type === "REP") {
          if (this.control["output_table"]) {
            this.control.output_table_columns = JSON.parse(this.control["output_table"]).columns;
          }
          this.getDatasourceColumns(this.control.source_name).then((data) => (this.datasourceColumns = data));
          this.getDatasourceColumns(this.control.source_name, "date").then((data) => (this.datasourceDateColumns = data));
        } else if (this.control.control_type === "REC") {
          if (this.control["output_table_a"]) {
            this.control.output_table_a_columns = JSON.parse(this.control["output_table_a"]).columns;
          }
          this.getDatasourceColumns(this.control.source_name_a).then((data) => (this.datasourceAColumns = data));
          this.getDatasourceColumns(this.control.source_name_a, "date").then((data) => (this.datasourceADateColumns = data));
          this.getDatasourceColumns(this.control.source_name_a, "numeric").then((data) => (this.datasourceANumColumns = data));

          if (this.control["output_table_b"]) {
            this.control.output_table_b_columns = JSON.parse(this.control["output_table_b"]).columns;
          }
          this.getDatasourceColumns(this.control.source_name_b).then((data) => (this.datasourceBColumns = data));
          this.getDatasourceColumns(this.control.source_name_b, "date").then((data) => (this.datasourceBDateColumns = data));
          this.getDatasourceColumns(this.control.source_name_b, "numeric").then((data) => (this.datasourceBNumColumns = data));
        } else if (this.control.control_type === "CMP") {
          this.cmpOutputTable = this.normalizeOutputColumns(this.control.output_table ? JSON.parse(this.control.output_table).columns : []);

          this.getDatasourceColumns(this.control.source_name_a).then((data) => (this.datasourceAColumns = data));
          this.getDatasourceColumns(this.control.source_name_a, "date").then((data) => (this.datasourceADateColumns = data));

          this.getDatasourceColumns(this.control.source_name_b).then((data) => (this.datasourceBColumns = data));
          this.getDatasourceColumns(this.control.source_name_b, "date").then((data) => (this.datasourceBDateColumns = data));
        }

        // The editor boxes edit these in place, so REC and CMP always get an object/array (also for a stored "null").
        const ruleConfig = this.control.rule_config ? JSON.parse(this.control.rule_config) : null;
        if (this.control.control_type === "REC") {
          this.ruleConfigObject = ruleConfig || this.defaultReconciliationRuleConfig();
        } else if (this.control.control_type === "CMP") {
          this.ruleConfigObject = ruleConfig || [];
        } else {
          this.ruleConfigObject = ruleConfig;
        }

        this.scheduleObject = this.control.schedule_config ? parseSchedule(this.control.schedule_config) : defaultSchedule();

        if (this.control.control_type === "CMP") {
          this.ruleErrorObject = (this.control.error_definition && JSON.parse(this.control.error_definition)) || [];
        }

        if (this.control.case_config) {
          this.caseConfigObject = JSON.parse(this.control.case_config);
        } else {
          this.caseConfigObject = [];
        }

        if (this.control.iteration_config) {
          this.iterationConfigObject = JSON.parse(this.control.iteration_config);
        } else {
          this.iterationConfigObject = [];
        }

        this.withDeleteionDrop = this.control.with_drop === "Y" ? "drop" : this.control.with_deletion === "Y" ? "deletion" : "N";
      } catch (err) {
        console.log(err);
      }
    },
    controlVersionChanged() {
      const oldVersion = this.controlVersions[0];
      const newVersion = this.controlVersion;
      // iterate through oldVersion and newVersion and locate differences and create an array of changes
      this.versionChanges = [];
      for (const key in oldVersion) {
        if (oldVersion[key] !== newVersion[key] && key !== "label" && key !== "audit_date" && key !== "updated_date" && key !== "updated_by") {
          this.versionChanges.push({
            field: key,
            oldValue: oldVersion[key],
            newValue: newVersion[key],
          });
        }
      }
      this.loadControl(newVersion);
    },
    // Edit a copy: the catalogue and version rows must not see unsaved edits.
    async loadControl(data, kpiControlName = null) {
      this.initializing = true;
      this.control = JSON.parse(JSON.stringify(data));
      this.initializeControl();
      this.loadControlKpis(kpiControlName || data.control_name);
      // Let the datasource watchers fire for this assignment before re-enabling them.
      await this.$nextTick();
      this.initializing = false;
    },
    deletionDropChanged() {
      if (this.withDeleteionDrop === "N") {
        this.control.with_deletion = "N";
        this.control.with_drop = "N";
      } else if (this.withDeleteionDrop === "deletion") {
        this.control.with_deletion = "Y";
        this.control.with_drop = "N";
      } else if (this.withDeleteionDrop === "drop") {
        this.control.with_deletion = "N";
        this.control.with_drop = "Y";
      }
    },
    addNewLineIfLastLineStartsWithDoubleDash(str) {
      if (str && str.includes("--") && str.substr(str.length - 1) != "\n") {
        return str + "\n";
      }
      return str;
    },
    async save() {
      // Add new line if last line contains a comment to avoid RAPO SQL builder issue
      this.control.source_filter = this.addNewLineIfLastLineStartsWithDoubleDash(this.control.source_filter);
      this.control.source_filter_a = this.addNewLineIfLastLineStartsWithDoubleDash(this.control.source_filter_a);
      this.control.source_filter_b = this.addNewLineIfLastLineStartsWithDoubleDash(this.control.source_filter_b);

      this.control.schedule_config = serializeSchedule(this.scheduleObject);

      // ANL rule
      if (this.control.control_type === "ANL") {
        if (!this.control.output_table_columns) {
          this.control.output_table = null;
        } else {
          this.control.output_table = JSON.stringify({
            columns: this.control.output_table_columns,
          });
        }

        if (this.caseConfigObject.length > 0) {
          this.control.case_config = JSON.stringify(this.caseConfigObject);
        } else {
          this.control.case_config = null;
        }
      }

      // REP rule
      if (this.control.control_type === "REP") {
        if (!this.control.output_table_columns) {
          this.control.output_table = null;
        } else {
          this.control.output_table = JSON.stringify({
            columns: this.control.output_table_columns,
          });
        }
      }

      // REC rule
      if (this.control.control_type === "REC") {
        // output limit should not be used for REC rules - instead use output_limit_a and output_limit_b in rule_config
        this.control.output_limit = null;

        if (!this.control.output_table_a_columns) {
          this.control.output_table_a = null;
        } else {
          this.control.output_table_a = JSON.stringify({
            columns: this.control.output_table_a_columns,
          });
        }

        if (!this.control.output_table_b_columns) {
          this.control.output_table_b = null;
        } else {
          this.control.output_table_b = JSON.stringify({
            columns: this.control.output_table_b_columns,
          });
        }

        if (this.ruleConfigObject.need_issues_a || this.ruleConfigObject.need_recons_a) {
          this.control.need_a = "Y";
        } else {
          this.control.need_a = "N";
        }

        if (this.ruleConfigObject.need_issues_b || this.ruleConfigObject.need_recons_b) {
          this.control.need_b = "Y";
        } else {
          this.control.need_b = "N";
        }

        if (!this.control.source_key_field_a) {
          this.control.source_key_field_a = "TAG";
        }
        if (!this.control.source_key_field_b) {
          this.control.source_key_field_b = "TAG";
        }

        this.control.rule_config = JSON.stringify(this.ruleConfigObject);
      }

      // CMP rule
      if (this.control.control_type === "CMP") {
        this.control.output_table_a = null;
        this.control.output_table_b = null;

        this.cmpOutputTable = this.normalizeOutputColumns(this.cmpOutputTable);
        this.control.output_table = JSON.stringify({
          columns: this.cmpOutputTable,
        });

        this.control.error_definition = JSON.stringify(this.ruleErrorObject);

        this.control.rule_config = JSON.stringify(this.ruleConfigObject);

        if (this.caseConfigObject.length > 0) {
          this.control.case_config = JSON.stringify(this.caseConfigObject);
        } else {
          this.control.case_config = null;
        }
      }

      if (this.iterationConfigObject.length > 0) {
        this.control.iteration_config = JSON.stringify(this.iterationConfigObject);
      } else {
        this.control.iteration_config = null;
      }

      // The KPIs are stored outside rapo_config, so they travel beside the control's own columns. The key
      // is left out entirely when there are no KPI tables, which tells the server not to touch them.
      const body = this.kpiAvailable ? { ...this.control, kpi_config: this.kpiConfigObject } : this.control;

      this.saving = true;
      try {
        await api("save-control", { method: "POST", body });
      } catch (error) {
        // stay on the page so unsaved edits are not lost
        this.saving = false;
        notifyError("Control was not saved.", error);
        return;
      }
      this.$q.notify({ type: "positive", message: "Control: " + this.control.control_name + " was saved successfully." });
      this.$router.push({ name: "controls" });
    },
    isBlank(value) {
      // Number inputs give "" when cleared; 0 is a valid value.
      return value == null || value === "";
    },
    validateAndSave() {
      var errorTab = null;
      if (!this.control.control_name) {
        this.$q.notify({
          type: "negative",
          message: "Please enter a control name.",
        });
        errorTab = "main";
      } else if (this.control.with_drop === "N" && this.control.with_deletion === "N" && !this.control.days_retention) {
        this.$q.notify({
          type: "negative",
          message: "Please select data retention period",
        });
        errorTab = "main";
      } else if (this.control.instance_limit == null || this.control.instance_limit < 1) {
        this.$q.notify({
          type: "negative",
          message: "Please select instance limit greater than 0",
        });
        errorTab = "main";
      } else if (this.control.control_type === "REC" || this.control.control_type === "CMP") {
        if (!this.control.source_name_a || !this.control.source_name_b) {
          this.$q.notify({
            type: "negative",
            message: "Please select a data source for both A and B.",
          });
          errorTab = "data";
        } else if (this.control.control_type === "REC" && (!this.control.source_date_field_a || !this.control.source_date_field_b)) {
          this.$q.notify({
            type: "negative",
            message: "Please select a date columns for both A and B datasources.",
          });
          errorTab = "data";
        }
      } else if ((this.control.control_type === "ANL" || this.control.control_type === "REP") && !this.control.source_name) {
        this.$q.notify({
          type: "negative",
          message: "Please select a data source.",
        });
        errorTab = "data";
      }

      if (!errorTab && (this.isBlank(this.control.period_back) || this.isBlank(this.control.period_number))) {
        this.$q.notify({
          type: "negative",
          message: "Please enter a period back and number of periods.",
        });
        errorTab = "scheduler";
      }

      if (!errorTab) {
        this.save(); // Call your save method
      } else {
        this.tab = errorTab;
      }
    },
    cancel() {
      this.$q.notify({
        type: "warning",
        message: "Changes discarded",
      });
      this.$router.push({ name: "controls" });
    },
    recreateSchema(control) {
      this.$q
        .dialog({
          title: control.control_name,
          message: "Recreate result tables? Past discrepancies will be deleted!",
          cancel: true,
          persistent: true,
        })
        .onOk(async () => {
          try {
            await api("delete-control-output-tables", { method: "DELETE", params: { name: control.control_name } });
            this.$q.notify({ type: "positive", message: "Schema for " + control.control_name + " was deleted. It will be recreated on the next run." });
          } catch (error) {
            notifyError("Schema deletion for " + control.control_name + " failed.", error);
          }
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
        });
    },
    // SQL selecting the source records a run fetched: side "T" for single-source controls, "A"/"B" otherwise.
    copyFetchSql(log, side) {
      if (this.control.control_type === "REP" && side === "B") {
        this.$q.notify({ type: "negative", message: "Source B SQL generation is not possible for Reports." });
        return;
      }
      const suffix = side === "T" ? "" : "_" + side.toLowerCase();
      const table = this.control["source_name" + suffix];
      const dateField = this.control["source_date_field" + suffix];
      const filter = this.control["source_filter" + suffix] || "1=1";
      const toDate = (value) => `to_date('${toDateTimeString(value)}' , 'YYYY-MM-DD HH24:MI:SS')`;
      const period = dateField ? `${dateField} between ${toDate(log.date_from)}\n\tand ${toDate(log.date_to)}\n\tand ` : "";
      copySql(`select * from ${table}\nwhere ${period}${filter};`, `Fetched records ${side === "T" ? "A" : side}-side`);
    },
    startLiveUpdates() {
      const stopLogs = liveRefetch("runs:changed", this.updateLogDaysBack, {
        filter: (payload) => payload.control_names.includes(this.control.control_name),
      });
      const stopConfig = liveRefetch("controls:changed", this.checkControlChanged, {
        filter: (payload) => payload.control_ids.includes(this.control.control_id),
      });
      this.stopLiveUpdates = () => {
        stopLogs();
        stopConfig();
      };
    },
    async checkControlChanged() {
      // Own save triggers this event too, and clones have nothing to compare.
      if (this.saving || !this.control.control_id) {
        return;
      }
      await this.updateControlCatalogue();
      const latest = this.controlCatalogueById(this.controlId);
      if (!latest) {
        this.$q.notify({ type: "warning", message: "This control was deleted by someone else.", timeout: 0, actions: [{ label: "Close", color: "white" }] });
        return;
      }
      if (latest.updated_date === this.loadedUpdatedDate) {
        return;
      }
      this.loadedUpdatedDate = latest.updated_date;
      this.$q.notify({
        type: "warning",
        message: "This control was changed by someone else.",
        caption: "Reload to see the latest version, your unsaved changes will be lost.",
        timeout: 0,
        actions: [
          { label: "Reload", color: "white", handler: () => this.reloadControl(latest) },
          { label: "Ignore", color: "white" },
        ],
      });
    },
    reloadControl(latest) {
      this.versionChanges = [];
      this.loadControl(latest);
      this.getControlVersions(this.controlId);
    },
  },
  watch: {
    "control.source_name": function (newDatasource, oldDatasource) {
      if (this.initializing) {
        return;
      }
      if (newDatasource && newDatasource !== oldDatasource) {
        this.getDatasourceColumns(newDatasource).then((data) => {
          this.datasourceColumns = data;
          this.control.output_table_columns = null;
        });

        this.getDatasourceColumns(newDatasource, "date").then((data) => {
          this.datasourceDateColumns = data;
          this.control.source_date_field = data[0];
        });
      }
    },
    "control.source_name_a": function (newDatasource, oldDatasource) {
      if (this.initializing) {
        return;
      }
      if (newDatasource && newDatasource !== oldDatasource) {
        this.getDatasourceColumns(newDatasource).then((data) => {
          this.datasourceAColumns = data;
          this.control.output_table_a_columns = null;
        });

        this.getDatasourceColumns(newDatasource, "date").then((data) => {
          this.datasourceADateColumns = data;
          this.control.source_date_field_a = data[0];
        });
      }

      this.getDatasourceColumns(newDatasource, "numeric").then((data) => {
        this.datasourceANumColumns = data;
      });
    },
    "control.source_name_b": function (newDatasource, oldDatasource) {
      if (this.initializing) {
        return;
      }
      if (newDatasource && newDatasource !== oldDatasource) {
        this.getDatasourceColumns(newDatasource).then((data) => {
          this.datasourceBColumns = data;
        });

        this.getDatasourceColumns(newDatasource, "date").then((data) => {
          this.datasourceBDateColumns = data;
          this.control.source_date_field_b = data[0];
        });

        this.getDatasourceColumns(newDatasource, "numeric").then((data) => {
          this.datasourceBNumColumns = data;
        });
      }
    },
  },
  async mounted() {
    this.getDatasources();
    // Both are usually cached. The KPI types must be in before loadControl, which reads kpiAvailable; a new
    // control doesn't wait for them, its KPIs tab appears when they arrive.
    const kpiTypesLoaded = this.loadKpiTypes();

    let controlData = this.controlCatalogueById(this.controlId);

    if (!controlData && this.controlId != "new") {
      try {
        await this.updateControlCatalogue();
      } catch (error) {
        notifyError("Failed to load controls.", error);
      }
      controlData = this.controlCatalogueById(this.controlId);
    }

    if (controlData) {
      await kpiTypesLoaded;
      // Before the clone rename, so a clone starts with the KPIs of the control it was cloned from.
      const kpiControlName = controlData.control_name;
      if (this.$route.query.clone) {
        // Force insert instead of update
        controlData = { ...controlData, control_id: undefined, control_name: controlData.control_name + "_CLONE" };
      }
      await this.loadControl(controlData, kpiControlName);
      this.ready = true;
      if (this.control.control_id) {
        this.getControlVersions(this.controlId);
        this.getControlLogs(this.control.control_name, this.log_days_back);
      }
      this.loadedUpdatedDate = this.control.updated_date;
      this.startLiveUpdates();
    } else {
      // NEW CONTROL
      this.control = {
        control_engine: "DB",
        control_type: "ANL",
        status: "Y",
        need_hook: "Y",
        need_postrun_hook: "Y",
        need_prerun_hook: "N",
        with_deletion: "N",
        with_drop: "N",
        days_back: 1,
        days_retention: 90,
        parallelism: 1,
        instance_limit: 1,
        period_type: "D",
        period_back: 1,
        period_number: 1,
      };
      this.ready = true;
    }
  },
  unmounted() {
    if (this.stopLiveUpdates) {
      this.stopLiveUpdates();
    }
  },
};
</script>

<style lang="css" scoped>
.new-day-separator > td {
  border-top: 2px solid #cfd8dc !important;
}
</style>
