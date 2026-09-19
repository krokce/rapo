<template>
  <q-page>
    <div>
      <h2 class="row">
        <q-chip
          size="xl"
          text-color="white"
          :class="{
            'bg-pink-8': control.control_type === 'ANL',
            'bg-teal-8': control.control_type === 'REC',
            'bg-lime-8': control.control_type === 'CMP',
            'bg-indigo-6': control.control_type === 'REP',
          }"
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
          :class="{
            'bg-pink-8': control.control_type === 'ANL',
            'bg-teal-8': control.control_type === 'REC',
            'bg-lime-8': control.control_type === 'CMP',
            'bg-indigo-6': control.control_type === 'REP',
          }"
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
                    class="col-2"
                    outlined
                    v-model="controlVersion"
                    use-input
                    hide-selected
                    fill-input
                    input-debounce="0"
                    label="Version"
                    :options="controlVersions"
                    @filter="filterDatasourceList"
                    @update:model-value="controlVersionChanged">
                    <template v-slot:prepend>
                      <q-icon
                        name="fas fa-tag"
                        size="sm"
                        @click="showVersionChanges"
                        @click.stop.prevent
                        class="cursor-pointer"
                        :class="{ 'text-deep-orange-4': this.versionChanges.length }">
                        <q-badge rounded size="xs" v-if="versionChanges.length" color="green" floating>{{ versionChanges.length }}</q-badge>
                        <q-tooltip v-if="this.versionChanges.length" anchor="top left" self="bottom left" :offset="[0, 5]"> Show changes </q-tooltip>
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
                    :options="[
                      { label: 'ANL - Analysis', value: 'ANL' },
                      { label: 'REC - Reconciliation', value: 'REC' },
                      { label: 'CMP - Comparison', value: 'CMP' },
                      { label: 'REP - Report', value: 'REP' },
                      // { label: 'Key Performance Indicator', value: 'KPI' },
                    ]"
                    label="Control type"
                    @update:model-value="controlTypeChanged" />

                  <q-select
                    class="col"
                    outlined
                    readonly
                    emit-value
                    map-options
                    v-model="control.control_engine"
                    :options="[
                      { label: 'Database', value: 'DB' },
                      { label: 'Python', value: 'PY' },
                    ]"
                    label="Control engine" />

                  <q-select
                    class="col"
                    outlined
                    emit-value
                    map-options
                    v-model="control.need_prerun_hook"
                    :options="[
                      { label: 'Yes', value: 'Y' },
                      { label: 'No', value: 'N' },
                    ]"
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
                    :options="[
                      { label: 'Yes', value: 'Y' },
                      { label: 'No', value: 'N' },
                    ]"
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
                  <q-btn label="Recreate schema" color="red" flat class="q-ml-auto" @click="recreateSchema(control)" />
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
                      v-model="this.cmpOutputTable"
                      :datasource-a-columns="this.datasourceAColumns"
                      :datasource-b-columns="this.datasourceBColumns">
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
                    <code-box label="Filter" v-model="control.source_filter"> </code-box>
                  </div>
                  <div class="col" v-if="control.control_type === 'REC' || control.control_type === 'CMP'">
                    <code-box label="Filter (Datasource A)" v-model="control.source_filter_a"> </code-box>
                  </div>
                  <div class="col" v-if="control.control_type === 'REC' || control.control_type === 'CMP'">
                    <code-box label="Filter (Datasource B)" v-model="control.source_filter_b"> </code-box>
                  </div>
                </div>

                <div class="row q-my-xs q-gutter-md" v-if="control.control_type == 'ANL'">
                  <div class="col">
                    <code-box label="Mismatch criteria (Error definition)" v-model="control.error_definition"> </code-box>
                  </div>
                </div>

                <div class="row q-my-xs q-gutter-md" v-if="control.control_type == 'CMP'">
                  <div class="col">
                    <!-- <code-box label="Match criteria (Rule config)" v-model="control.rule_config"> </code-box> -->
                    <comparison-match-criteria-box
                      class="col"
                      v-model="this.ruleConfigObject"
                      :datasource-a-columns="this.datasourceAColumns"
                      :datasource-b-columns="this.datasourceBColumns">
                    </comparison-match-criteria-box>
                  </div>
                  <div class="col">
                    <!-- <code-box label="Mismatch criteria (Error definition)" v-model="control.error_definition"> </code-box> -->
                    <comparison-mis-match-criteria-box
                      class="col"
                      v-model="this.ruleErrorObject"
                      :datasource-a-columns="this.datasourceAColumns"
                      :datasource-b-columns="this.datasourceBColumns">
                    </comparison-mis-match-criteria-box>
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
                    v-model="this.ruleConfigObject"
                    :datasource-a-columns="this.datasourceAColumns"
                    :datasource-b-columns="this.datasourceBColumns">
                  </reconciliation-match-criteria-box>

                  <reconciliation-mis-match-criteria-box
                    class="col"
                    v-model="this.ruleConfigObject"
                    :datasource-a-columns="this.datasourceANumColumns"
                    :datasource-b-columns="this.datasourceBNumColumns">
                  </reconciliation-mis-match-criteria-box>

                  <reconciliation-discrepancy-checkboxes class="col" :control="control" v-model="this.ruleConfigObject">
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
                    <code-box label="Preparation SQL" v-model="control.preparation_sql"></code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[-120, -20]">
                      Preparation SQL is executed before the control is started. It can be used to prepare the data for the control. See the enclosed examples.
                    </q-tooltip>
                  </div>
                </div>

                <div class="row q-gutter-md">
                  <div class="col">
                    <code-box label="Prerequisite SQL" v-model="control.prerequisite_sql"> </code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[-120, -20]">
                      Prerequisite SQL is executed before the control is started. If the number returned is 0 the control will be terminated. See the enclosed
                      positive and negative examples.
                    </q-tooltip>
                  </div>
                </div>

                <div class="row q-gutter-md">
                  <div class="col">
                    <code-box label="Completion SQL" v-model="control.completion_sql"> </code-box>
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
                    <!-- <code-box label="Case config" v-model="control.case_config"> </code-box> -->
                    <case-config-box class="col" v-model="this.caseConfigObject"> </case-config-box>
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
                    :options="[
                      { label: 'Day', value: 'D' },
                      { label: 'Week', value: 'W' },
                      { label: 'Month', value: 'M' },
                    ]"
                    label="Period type" />
                </div>

                <div v-if="scheduleType !== 'C'" class="row q-gutter-md">
                  <iteration-config-box class="col" v-model="iterationConfigObject" :pb="this.control.period_back"> </iteration-config-box>
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
                    <tr class="cursor-pointer" v-for="(control_log, index) in controlLogs" :key="control_log.process_id">
                      <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }">{{ index + 1 }}. &nbsp;</td>
                      <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <div class="text-blue-grey-7">
                          <strong>{{ toDateString(control_log.added) }}</strong>
                          <small class="text-grey-7 q-px-sm">{{ toTimeString(control_log.added) }}</small>
                        </div>
                      </td>
                      <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <div class="text-blue-grey-7">
                          <strong>{{ toDateString(control_log.start_date) }}</strong>
                          <small class="text-grey-7 q-px-sm">{{ toTimeString(control_log.start_date) }}</small>
                        </div>
                      </td>
                      <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <div class="text-blue-grey-7">
                          <strong>{{ toDateString(control_log.end_date) }}</strong>
                          <small class="text-grey-7 q-px-sm">{{ toTimeString(control_log.end_date) }}</small>
                        </div>
                      </td>
                      <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        {{
                          control_log.end_date && control_log.start_date
                            ? round((new Date(control_log.end_date) - new Date(control_log.start_date)) / 60000, 1)
                            : "0"
                        }}
                        min
                      </td>

                      <td class="text-left text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        {{ control_log.process_id }}
                      </td>
                      <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }">{{ toDateString(control_log.date_from) }}</td>
                      <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }">{{ toDateString(control_log.date_to) }}</td>

                      <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <span
                          v-if="Number(control_log.fetched_number_a) + Number(control_log.fetched_number) > 0 && control.control_type === 'REP'"
                          class="cursor-pointer text-red"
                          @click="copyToClipboard(control_log, 'A')">
                          {{
                            (Number(control_log.fetched_number_a) + Number(control_log.fetched_number)).toLocaleString(undefined, {
                              minimumFractionDigits: 0,
                              maximumFractionDigits: 0,
                            })
                          }}
                        </span>
                        <span v-else @click="copyFetchSQLToClipboard(control_log, this.control.control_type == 'ANL' ? 'T' : 'A')">
                          {{
                            (Number(control_log.fetched_number_a) + Number(control_log.fetched_number)).toLocaleString(undefined, {
                              minimumFractionDigits: 0,
                              maximumFractionDigits: 0,
                            })
                          }}
                        </span>
                      </td>
                      <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <span @click="copyFetchSQLToClipboard(control_log, this.control.control_type == 'ANL' ? 'T' : 'B')">
                          {{
                            Number(control_log.fetched_number_b).toLocaleString(undefined, {
                              minimumFractionDigits: 0,
                              maximumFractionDigits: 0,
                            })
                          }}
                        </span>
                      </td>
                      <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <span
                          v-if="Number(control_log.error_number_a) + Number(control_log.error_number) > 0"
                          class="cursor-pointer text-red"
                          @click="copyToClipboard(control_log, 'A')">
                          {{
                            (Number(control_log.error_number_a) + Number(control_log.error_number)).toLocaleString(undefined, {
                              minimumFractionDigits: 0,
                              maximumFractionDigits: 0,
                            })
                          }}
                        </span>
                        <span v-else>
                          {{
                            (Number(control_log.error_number_a) + Number(control_log.error_number)).toLocaleString(undefined, {
                              minimumFractionDigits: 0,
                              maximumFractionDigits: 0,
                            })
                          }}
                        </span>
                      </td>
                      <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <span v-if="control_log.error_number_b > 0" class="cursor-pointer text-red" @click="copyToClipboard(control_log, 'B')">
                          {{ Number(control_log.error_number_b).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
                        </span>
                        <span v-else>
                          {{ Number(control_log.error_number_b).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
                        </span>
                      </td>
                      <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <span
                          v-if="Number(control_log.error_level_a) + Number(control_log.error_level) > 0"
                          class="cursor-pointer text-red"
                          @click="copyToClipboard(control_log, 'A')">
                          {{
                            (Number(control_log.error_level_a) + Number(control_log.error_level)).toLocaleString(undefined, {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })
                          }}%
                        </span>
                        <span v-else>
                          {{
                            (Number(control_log.error_level_a) + Number(control_log.error_level)).toLocaleString(undefined, {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })
                          }}%
                        </span>
                      </td>
                      <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <span v-if="control_log.error_level_b > 0" class="cursor-pointer text-red" @click="copyToClipboard(control_log, 'B')">
                          {{ Number(control_log.error_level_b).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}%
                        </span>
                        <span v-else>
                          {{ Number(control_log.error_level_b).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}%
                        </span>
                      </td>
                      <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <q-icon v-if="control_log.prerequisite_value == 0" class="cursor-pointer text-red" name="fas fa-stop">
                          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Prerequisite SQL value is 0 </q-tooltip>
                        </q-icon>
                        <q-icon v-if="control_log.prerequisite_value" class="cursor-pointer text-green" name="fas fa-play">
                          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                            Prerequisite SQL value is {{ control_log.prerequisite_value }}
                          </q-tooltip>
                        </q-icon>
                      </td>
                      <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <q-chip class="cursor-pointer">
                          <q-avatar v-if="control_log.status == 'I'" icon="fas fa-plus-circle" color="indigo" text-color="white" />
                          <q-avatar v-if="control_log.status == 'W'" icon="fas fa-pause-circle" color="amber-7" text-color="white" />
                          <q-avatar v-if="control_log.status == 'S'" icon="fas fa-play-circle" color="blue" text-color="white" />
                          <q-avatar v-if="control_log.status == 'P'" icon="fas fa-sync fa-spin" color="blue" text-color="white" />
                          <q-avatar v-if="control_log.status == 'F'" icon="fas fa-circle-notch fa-spin" color="blue" text-color="white" />
                          <q-avatar v-if="control_log.status == 'D'" icon="fas fa-check-circle" color="green" text-color="white" />
                          <q-avatar v-if="control_log.status == 'C'" icon="fas fa-times-circle" color="purple-3" text-color="white" />
                          <q-avatar v-if="control_log.status == 'E'" icon="fas fa-exclamation-circle" color="deep-orange" text-color="white" />
                          <q-avatar v-if="control_log.status == 'X'" icon="fas fa-times-circle" color="grey" text-color="white" />
                          <q-avatar v-if="!control_log.status" icon="fas fa-times-circle" color="deep-purple-3" text-color="white" />
                          {{
                            control_log.status === "I"
                              ? "Initiated"
                              : control_log.status === "W"
                              ? "Waiting"
                              : control_log.status === "S"
                              ? "Started"
                              : control_log.status == "P"
                              ? "Running"
                              : control_log.status === "F"
                              ? "Finishing"
                              : control_log.status === "D"
                              ? "Done"
                              : control_log.status === "E"
                              ? "Error"
                              : control_log.status === "C"
                              ? "Canceled"
                              : control_log.status === "X"
                              ? "Revoked"
                              : !control_log.status
                              ? "Void"
                              : "Unknown"
                          }}
                        </q-chip>
                      </td>
                      <td class="text-left" style="width: 50px" :class="{ 'new-day-separator': newDaySeparator(index) }">
                        <q-btn size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v">
                          <q-menu>
                            <q-list dense class="text-no-wrap">
                              <q-item dense clickable @click="reRun(control_log)" v-close-popup>
                                <q-item-section> Re-run </q-item-section>
                              </q-item>
                              <q-separator />
                              <q-item
                                v-if="
                                  control_log.status == 'F' ||
                                  control_log.status == 'I' ||
                                  control_log.status == 'W' ||
                                  control_log.status == 'S' ||
                                  control_log.status == 'P'
                                "
                                dense
                                clickable
                                class="col items-center"
                                @click="showCancelDialog(control_log)"
                                v-close-popup>
                                <q-item-section> Cancel run </q-item-section>
                              </q-item>
                              <q-item
                                v-if="control_log.status != 'X'"
                                dense
                                clickable
                                class="col items-center"
                                @click="showRevokeDialog(control_log)"
                                v-close-popup>
                                <q-item-section> Revoke run </q-item-section>
                              </q-item>
                              <q-item dense clickable class="col items-center" @click="showFullLog(control_log)" v-close-popup>
                                <q-item-section> Show full log </q-item-section>
                              </q-item>
                              <q-item dense clickable @click="dropTemporaryTables(control_log)" v-close-popup>
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
                <!-- <pre class="bg-grey-2 q-pa-sm" style="overflow: auto">
                      {{ formattedJSON }}
              </pre>
               -->
              </div>
            </q-tab-panel>
          </q-tab-panels>
        </q-form>
      </q-card>
    </div>

    <!-- <p class="q-ma-xl">{{ control }}</p> -->
  </q-page>
</template>

<script>
import { useQuasar } from "quasar";
import { mapActions, mapGetters } from "vuex";
import CodeBox from "./CodeBox.vue";
import ScheduleEditBox from "./ScheduleEditBox.vue";
import ReconciliationDiscrepancyCheckboxes from "./ReconciliationDiscrepancyCheckboxes.vue";
import ReconciliationMatchCriteriaBox from "./ReconciliationMatchCriteriaBox.vue";
import ReconciliationMisMatchCriteriaBox from "./ReconciliationMisMatchCriteriaBox.vue";
import CaseConfigBox from "./CaseConfigBox.vue";
import IterationConfigBox from "./IterationConfigBox.vue";
import ComparisonMatchCriteriaBox from "./ComparisonMatchCriteriaBox.vue";
import ComparisonMisMatchCriteriaBox from "./ComparisonMisMatchCriteriaBox.vue";
import ComparisonOutputTableBox from "./ComparisonOutputTableBox.vue";

export default {
  components: {
    CodeBox,
    ScheduleEditBox,
    ReconciliationDiscrepancyCheckboxes,
    ReconciliationMatchCriteriaBox,
    ReconciliationMisMatchCriteriaBox,
    CaseConfigBox,
    IterationConfigBox,
    ComparisonMatchCriteriaBox,
    ComparisonMisMatchCriteriaBox,
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
      datasourceListAOptions: null,
      datasourceListBOptions: null,
      withDeleteionDrop: "N",
      scheduleObject: {
        mday: null,
        wday: null,
        hour: "8",
        min: "15",
        sec: "0",
        trigger_id: null,
      },
      ruleConfigObject: {},
      cmpOutputTable: [],
      ruleErrorObject: null,
      caseConfigObject: [],
      iterationConfigObject: [],
      controlLogs: [],
      versionChanges: [],
      $q: useQuasar(),
    };
  },
  computed: {
    ...mapGetters(["controlCatalogueById"]),
    scheduleType() {
      // Determine schedule type
      if (
        String(this.schedule_config).indexOf("/") > -1 ||
        String(this.schedule_config).indexOf("-") > -1 ||
        (String(this.scheduleObject.mday).indexOf(",") > -1 && String(this.scheduleObject.wday).indexOf(",") > -1) ||
        (String(this.scheduleObject.hour) + String(this.scheduleObject.min) + String(this.scheduleObject.sec)).indexOf(",") > -1
      ) {
        return "X";
      } else if (this.scheduleObject.hour == null && this.scheduleObject.min == null && this.scheduleObject.sec == null) {
        return "C";
      } else if (this.scheduleObject.mday) {
        return "M";
      } else if (this.scheduleObject.wday) {
        return "W";
      } else {
        return "D";
      }
    },
  },
  methods: {
    ...mapActions(["updateControlCatalogue"]),
    updateLogDaysBack() {
      this.getControlLogs(this.control.control_name, this.log_days_back);
    },
    toDateString(val) {
      var ret = new Date(val).toISOString("de-DE").substring(0, 10);
      return ret;
    },
    toTimeString(val) {
      var ret = new Date(val).toISOString("de-DE").substring(11, 19);
      return ret;
    },
    toDateTimeString(val) {
      var ret = new Date(val).toISOString("de-DE").substring(0, 19).replace("T", " ");
      return ret;
    },
    round(val, places) {
      return Math.round(val * Math.pow(10, places)) / Math.pow(10, places);
    },
    showFullLog(control_log) {
      this.$q.dialog({
        title: this.control.control_name + " | " + " PID:" + control_log.process_id + " Full log",
        message: "<pre>" + this.formattedJSON(control_log) + "</pre>",
        html: true,
        style: {
          width: "800px", // Adjust the width as needed
          maxWidth: "90vw", // Optional: Ensure it doesn't exceed viewport width
        },
      });
    },
    showVersionChanges() {
      if (!this.versionChanges.length) {
        return;
      }
      this.$q.dialog({
        title: this.control.control_name + " | " + this.controlVersion.label,
        message: "<pre>" + this.formattedJSON(this.versionChanges) + "</pre>",
        html: true,
        style: {
          width: "800px", // Adjust the width as needed
          maxWidth: "90vw", // Optional: Ensure it doesn't exceed viewport width
        },
      });
    },
    formattedJSON(control) {
      return JSON.stringify(control, null, 2).replace(/\\"/g, "'");
    },
    filterDatasourceList(val, update, abort) {
      if (val.length < 0) {
        abort();
        return;
      }

      update(() => {
        const needle = val.toLowerCase();
        this.datasourceListOptions = this.datasourceList.filter((v) => v.toLowerCase().indexOf(needle) > -1);
      });

      // setTimeout(() => {
      //   update(() => {
      //     if (val === "") {
      //       this.datasourceListOptions = this.datasourceList;
      //     } else {
      //       const needle = val.toLowerCase();
      //       this.datasourceListOptions = this.datasourceList.filter(
      //         (v) => v.toLowerCase().indexOf(needle) > -1
      //       );
      //     }
      //   });
      // }, 500);
    },
    getDatasources() {
      this.$q.loadingBar.start();

      fetch("/api/get-datasources", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.$store.getters.getToken}`,
          "Content-Type": "application/json",
        },
      })
        .then((response) => {
          if (response.ok) {
            return response.json();
          }
        })
        .then((data) => {
          this.datasourceList = data;
          this.$q.loadingBar.stop();
        });
    },
    async getDatasourceColumns(datasource_name, which) {
      if (!datasource_name) {
        return [];
      }

      const response = await fetch("/api/get-datasource-columns?datasource_name=" + datasource_name, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.$store.getters.getToken}`,
          "Content-Type": "application/json",
        },
      });
      if (response.ok) {
        const data = await response.json();
        var ret;
        // data is array of objects {column_name, data_type}. Create an array containing only the columns from type `which`: NUMBER, VARCHAR2, DATE
        if (which === "numeric") {
          ret = data
            .filter(
              (item) =>
                item.data_type.toUpperCase().includes("NUMBER") ||
                item.data_type.toUpperCase().includes("FLOAT") ||
                item.data_type.toUpperCase().includes("DOUBLE") ||
                item.data_type.toUpperCase().includes("DECIMAL") ||
                item.data_type.toUpperCase().includes("INTEGER")
            )
            .map((item) => item.column_name);
        } else if (which === "string") {
          ret = data.filter((item) => item.data_type.toUpperCase().includes("CHAR")).map((item) => item.column_name);
        } else if (which === "date") {
          ret = data
            .filter((item) => item.data_type.toUpperCase().includes("TIMESTAMP") || item.data_type.toUpperCase() === "DATE")
            .map((item) => item.column_name);
          // ret.push(null);
        } else {
          ret = data.map((item) => item.column_name);
        }

        return ret;
      }
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
    controlTypeChanged(newValue) {
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
        this.ruleConfigObject = {
          need_issues_a: true,
          need_issues_b: true,
          need_recons_a: false,
          need_recons_b: false,
          output_limit_a: null,
          output_limit_b: null,
          allow_duplicates: false,
          correlation_limit: true,
          time_shift_from: 0,
          time_shift_to: 0,
          time_tolerance_from: 0,
          time_tolerance_to: 0,
          correlation_config: [],
          discrepancy_config: [],
        };

        this.control.source_key_field_a = "TAG";
        this.control.source_key_field_b = "TAG";
      } else if (newValue === "CMP") {
        this.ruleConfigObject = [];
        this.ruleErrorObject = [];
      } else if (newValue === "REP") {
        this.ruleConfigObject = {};
      } else if (newValue === "ANL") {
        this.ruleConfigObject = {};
      }
    },
    async getControlVersions(controlId) {
      const response = await fetch("/api/get-control-versions?control_id=" + controlId, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.$store.getters.getToken}`,
          "Content-Type": "application/json",
        },
      });
      if (response.ok) {
        const data = await response.json();
        this.controlVersions = data;
        this.controlVersions.forEach((element) => {
          element.label =
            "v." + new Date(element.updated_date ? element.updated_date : element.created_date).toISOString("de-DE").substring(0, 19).replace("T", " ");
        });
        this.control.label =
          "v." +
          new Date(this.control.updated_date ? this.control.updated_date : this.control.created_date).toISOString("de-DE").substring(0, 19).replace("T", " ");
        this.controlVersions.unshift(this.control);
        this.controlVersion = this.controlVersions[0];
      }
    },
    async getControlLogs(controlName, numberDays) {
      const response = await fetch("/api/read-control-logs?control_name=" + controlName + "&days=" + numberDays, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.$store.getters.getToken}`,
          "Content-Type": "application/json",
        },
      });
      if (response.ok) {
        const data = await response.json();
        this.controlLogs = data;
      }
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
          if (this.control["output_table"]) {
            this.cmpOutputTable = JSON.parse(this.control["output_table"]).columns;
            this.cmpOutputTable.forEach((element) => {
              for (const key in element) {
                if (element[key] === null) {
                  delete element[key];
                } else {
                  element[key] = element[key].toUpperCase();
                }
              }
            });
          }

          this.getDatasourceColumns(this.control.source_name_a).then((data) => (this.datasourceAColumns = data));
          this.getDatasourceColumns(this.control.source_name_a, "date").then((data) => (this.datasourceADateColumns = data));

          this.getDatasourceColumns(this.control.source_name_b).then((data) => (this.datasourceBColumns = data));
          this.getDatasourceColumns(this.control.source_name_b, "date").then((data) => (this.datasourceBDateColumns = data));
        }

        if (this.control.rule_config) {
          this.ruleConfigObject = JSON.parse(this.control.rule_config);
        } else {
          if (this.control.control_type === "REC") {
            this.ruleConfigObject = {
              need_issues_a: true,
              need_issues_b: true,
              need_recons_a: false,
              need_recons_b: false,
              allow_duplicates: false,
              time_shift_from: 0,
              time_shift_to: 0,
              time_tolerance_from: 0,
              time_tolerance_to: 0,
              correlation_config: [],
              discrepancy_config: [],
            };
          } else if (this.control.control_type === "CMP") {
            this.ruleConfigObject = [];
          } else if (this.control.control_type === "REP") {
            this.ruleConfigObject = null;
          } else if (this.control.control_type === "ANL") {
            this.ruleConfigObject = null;
          } else {
            this.ruleConfigObject = null;
          }
        }

        if (this.control.schedule_config) {
          this.scheduleObject = this.toScheduleObject(this.control.schedule_config);
        } else {
          this.scheduleObject = {
            mday: null,
            wday: null,
            hour: "8",
            min: "15",
            sec: "0",
            trigger_id: null,
          };
        }

        if (this.control.error_definition && this.control.control_type == "CMP") {
          this.ruleErrorObject = JSON.parse(this.control.error_definition);
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
      var oldVersion = this.controlVersions[0];
      this.control = this.controlVersion;
      // iterate through oldVersion and this.control and locate differences and create an array of changes
      this.versionChanges = [];
      for (const key in oldVersion) {
        if (oldVersion[key] !== this.control[key] && key !== "label" && key !== "audit_date" && key !== "updated_date" && key !== "updated_by") {
          this.versionChanges.push({
            field: key,
            oldValue: oldVersion[key],
            newValue: this.control[key],
          });
        }
      }
      this.initializeControl();
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
    toScheduleString(scheduleObject) {
      var ret = {
        mday: scheduleObject.mday ? String(scheduleObject.mday) : null,
        wday: scheduleObject.wday ? String(scheduleObject.wday) : null,
        hour: scheduleObject.hour != null ? String(scheduleObject.hour) : null,
        min: scheduleObject.min != null ? String(scheduleObject.min) : null,
        sec: scheduleObject.sec != null ? String(scheduleObject.sec) : null,
        trigger_id: scheduleObject.trigger_id ? scheduleObject.trigger_id : null,
      };
      return JSON.stringify(ret);
    },
    toScheduleObject(scheduleString) {
      var ret = {
        mday: null,
        wday: null,
        hour: "8",
        min: "15",
        sec: "0",
        trigger_id: null,
      };

      var scheduleType = null;

      if (scheduleString) {
        ret = JSON.parse(scheduleString);
        // Determine schedule type
        if (!scheduleType) {
          if (
            String(scheduleString).indexOf("/") > -1 ||
            String(scheduleString).indexOf("-") > -1 ||
            (String(ret.mday).indexOf(",") > -1 && String(ret.wday).indexOf(",") > -1) ||
            (String(ret.hour) + String(ret.min) + String(ret.sec)).indexOf(",") > -1
          ) {
            scheduleType = "X";
          } else if (!ret.hour && !ret.min && !ret.sec) {
            scheduleType = "C";
          } else if (ret.mday) {
            scheduleType = "M";
          } else if (ret.wday) {
            scheduleType = "W";
          } else {
            scheduleType = "D";
          }

          // Convert components to arrays in case of simple scheduler
          if (scheduleType !== "X") {
            if (ret.mday) {
              ret.mday = String(ret.mday)
                .split(",")
                .map((i) => Number(i));
            }

            if (ret.wday) {
              ret.wday = String(ret.wday)
                .split(",")
                .map((i) => Number(i));
            }
          }
        }
      }

      return ret;
    },
    save() {
      // Add new line if last line contains a comment to avoid RAPO SQL builder issue
      this.control.source_filter = this.addNewLineIfLastLineStartsWithDoubleDash(this.control.source_filter);
      this.control.source_filter_a = this.addNewLineIfLastLineStartsWithDoubleDash(this.control.source_filter_a);
      this.control.source_filter_b = this.addNewLineIfLastLineStartsWithDoubleDash(this.control.source_filter_b);

      this.control.schedule_config = this.toScheduleString(this.scheduleObject);

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

        this.control.output_table = [];

        // iterate over cmpOutputTable array and for each object elements
        // remove elements with value null and upercase those with values not null
        this.cmpOutputTable.forEach((element) => {
          for (const key in element) {
            if (element[key] === null) {
              delete element[key];
            } else {
              element[key] = element[key].toUpperCase();
            }
          }
        });

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

      fetch("/api/save-control", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.$store.getters.getToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(this.control),
      })
        .then((response) => {
          if (!response.ok) {
            this.$q.notify({
              type: "warning",
              message: "Network response was not ok: " + response,
            });
            this.$router.push({ name: "controls" });
          }
          return response.json();
        })
        // eslint-disable-next-line no-unused-vars
        .then((data) => {
          this.$q.notify({
            type: "positive",
            message: "Control: " + this.control.control_name + " was saved successfully.",
          });
          // reload "Controls" page if control attributes changed
          this.$router.push({ name: "controls" });
        })
        .catch((error) => {
          this.$q.notify({ type: "negative", message: "Error:" + error });
          this.$router.push({ name: "controls" });
        });
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
      } else if (this.control.control_type === "ANL" || this.control.control_type === "REP") {
        if (!this.control.source_name) {
          this.$q.notify({
            type: "negative",
            message: "Please select a data source.",
          });
          errorTab = "data";
        }
      } else if (!this.control.period_back || !this.control.period_number) {
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
        .onOk(() => {
          fetch("/api/delete-control-output-tables?name=" + control.control_name, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
          })
            .then((response) => {
              if (response.ok) {
                this.$q.notify({ type: "positive", message: "Schema for " + control.control_name + " was deleted. It will be recreated on the next run." });
              } else {
                this.$q.notify({ type: "negative", message: "Schema deletion for " + control.control_name + "' failed" });
              }
            })
            .then(() => {
              this.$q.loadingBar.stop();
            });
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
          // console.log('Cancel')
        });
    },
    copyFetchSQLToClipboard(control, side) {
      control.control_name = this.control.control_name;
      control.control_type = this.control.control_type;

      if (control.control_type == "REP") {
        this.$q.notify({ type: "negative", message: "Source B SQL generation is not possible for Reports." });
        return;
      }

      var statement = "";
      if (side == "A") {
        statement =
          "select * from " +
          this.control.source_name_a +
          "\nwhere " +
          this.control.source_date_field_a +
          " between to_date('" +
          this.toDateTimeString(control.date_from) +
          "' , 'YYYY-MM-DD HH24:MI:SS')\n\tand to_date('" +
          this.toDateTimeString(control.date_to) +
          "' , 'YYYY-MM-DD HH24:MI:SS')\n\tand " +
          (this.control.source_filter_a ? this.control.source_filter_a : "1=1") +
          ";";
      } else if (side == "B") {
        statement =
          "select * from " +
          this.control.source_name_b +
          "\nwhere " +
          this.control.source_date_field_b +
          " between to_date('" +
          this.toDateTimeString(control.date_from) +
          "' , 'YYYY-MM-DD HH24:MI:SS')\n\tand to_date('" +
          this.toDateTimeString(control.date_to) +
          "' , 'YYYY-MM-DD HH24:MI:SS')\n\tand " +
          (this.control.source_filter_b ? this.control.source_filter_b : "1=1") +
          ";";
      } else {
        statement =
          "select * from " +
          this.control.source_name +
          "\nwhere " +
          (this.control.source_date_field?(this.control.source_date_field +
          " between to_date('" +
          this.toDateTimeString(control.date_from) +
          "' , 'YYYY-MM-DD HH24:MI:SS')\n\tand to_date('" +
          this.toDateTimeString(control.date_to) +
          "' , 'YYYY-MM-DD HH24:MI:SS')\n\tand "):"") +
          (this.control.source_filter ? this.control.source_filter : "1=1") +
          ";";
      }

      const textarea = document.createElement("textarea");
      textarea.value = statement;
      textarea.style.position = "fixed";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      try {
        document.execCommand("copy");
        this.$q.notify({ type: "positive", message: "Fetched records " + (side=='T'?'A':side) + "-side SQL statement copied to clipboard: " + textarea.value });
      } catch (err) {
        this.$q.notify({ type: "negative", message: "Failed to copy SQL to clipboard" });
      }
      document.body.removeChild(textarea);
    },
    copyToClipboard(control, side) {
      control.control_name = this.control.control_name;
      control.control_type = this.control.control_type;

      var table_suffix = "T";
      if (control.control_type == "REC") {
        table_suffix = side;
      }

      const textarea = document.createElement("textarea");
      textarea.value = "select * from RAPO_RES" + table_suffix + "_" + control.control_name + " where RAPO_PROCESS_ID = " + control.process_id + ";";
      textarea.style.position = "fixed";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      try {
        document.execCommand("copy");
        this.$q.notify({ type: "positive", message: "Discrepancies " + (side=='T'?'A':side) + "-side SQL statement copied to clipboard: " + textarea.value });
      } catch (err) {
        this.$q.notify({ type: "negative", message: "Failed to copy SQL to clipboard" });
      }
      document.body.removeChild(textarea);
    },
    newDaySeparator(index) {
      if (index > 0) {
        const prev_date = this.toDateString(this.controlLogs[index - 1].added);
        const curr_date = this.toDateString(this.controlLogs[index].added);
        if (prev_date != curr_date) {
          return true;
        }
      }
      return false;
    },
    reRun(control) {
      control.control_name = this.control.control_name;

      this.$q
        .dialog({
          title: control.control_name,
          message:
            "Re-run for '" +
            this.toDateString(control.date_from) +
            "'" +
            (this.toDateString(control.date_from) != this.toDateString(control.date_to) ? " - '" + this.toDateString(control.date_to) + "'" : "") +
            "?",
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          var url =
            "/api/run-control?name=" +
            control.control_name +
            "&date_from=" +
            this.toDateTimeString(control.date_from) +
            "&date_to=" +
            this.toDateTimeString(control.date_to);

          fetch(url, {
            method: "POST",
            headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
          })
            .then((response) => {
              if (response.ok) {
                this.$q.notify({ type: "positive", message: "Control " + control.control_name + " queued for execution" });
                return response.json();
              } else {
                this.$q.notify({ type: "negative", message: "Control " + control.control_name + " failed" });
              }
            })
            .then(() => {
              this.$q.loadingBar.stop();
              this.getControlLogs(this.control.control_name, this.log_days_back);
              // this.refreshControlResults();
            });
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
          // console.log('Cancel')
        });
    },
    showCancelDialog(control) {
      control.control_name = this.control.control_name;

      this.$q
        .dialog({
          title: control.control_name,
          message: "Do you really want to stop the execution of this control?",
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          fetch("/api/cancel-control?id=" + control.process_id, {
            method: "POST",
            headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
          })
            .then((response) => {
              if (response.ok) {
                this.$q.notify({ type: "positive", message: "Control run '" + control.control_name + " PID:" + control.process_id + "' was canceled" });
                control.status = "C";
              } else {
                this.$q.notify({ type: "negative", message: "Stopping control run '" + control.control_name + " PID:" + control.process_id + "' failed" });
              }
            })
            .then(() => {
              this.$q.loadingBar.stop();
            });
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
          // console.log('Cancel')
        });
    },
    showRevokeDialog(control) {
      control.control_name = this.control.control_name;

      this.$q
        .dialog({
          title: control.control_name,
          message: "Do you really want to revoke this control run?",
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          fetch("/api/revoke-control-run?id=" + control.process_id, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
          })
            .then((response) => {
              if (response.ok) {
                this.$q.notify({ type: "positive", message: "Control run '" + control.control_name + " PID:" + control.process_id + "' was revoked" });
                control.status = "X";
              } else {
                this.$q.notify({ type: "negative", message: "Revoke of control run '" + control.control_name + " PID:" + control.process_id + "' failed" });
              }
            })
            .then(() => {
              this.$q.loadingBar.stop();
            });
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
          // console.log('Cancel')
        });
    },
    dropTemporaryTables(control) {
      control.control_name = this.control.control_name;

      this.$q
        .dialog({
          title: control.control_name,
          message: "Do you really want to drop all debug temporary tables for execution with PID: " + control.process_id + " ?",
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          fetch("/api/delete-control-temporary-tables?id=" + control.process_id, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
          })
            .then((response) => {
              if (response.ok) {
                this.$q.notify({ type: "positive", message: "All temporary tables for PID:" + control.process_id + " were deleted" });
              } else {
                this.$q.notify({ type: "negative", message: "Temporary tables deletion for PID:" + control.process_id + "' failed" });
              }
            })
            .then(() => {
              this.$q.loadingBar.stop();
            });
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
          // console.log('Cancel')
        });
    },
    startControlLogsRefreshTimer() {
      this.refreshTimer = setInterval(this.updateLogDaysBack, 5000);
    },
    stopControlLogsRefreshTimer() {
      clearInterval(this.refreshTimer);
    },
  },
  watch: {
    "control.source_name": function (newDatasource, oldDatasource) {
      if ((oldDatasource && newDatasource && oldDatasource !== newDatasource) || !this.control.control_id) {
        this.getDatasourceColumns(newDatasource).then((data) => {
          this.datasourceColumns = data;
          // this.control.output_table_columns = data;
          this.control.output_table_columns = null;
          // this.control.source_filter = "-- Columns:" + JSON.stringify(data) + "\n";
        });

        this.getDatasourceColumns(newDatasource, "date").then((data) => {
          this.datasourceDateColumns = data;
          this.control.source_date_field = data[0];
          // this.control.source_date_field = null;
        });
      }
    },
    "control.source_name_a": function (newDatasource, oldDatasource) {
      if ((oldDatasource && newDatasource && oldDatasource !== newDatasource) || !this.control.control_id) {
        this.getDatasourceColumns(newDatasource).then((data) => {
          this.datasourceAColumns = data;
          // this.control.source_filter_a = "-- Columns:" + JSON.stringify(data) + "\n";
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
      // this.control.source_filter_b = "";
      if ((oldDatasource && newDatasource && oldDatasource !== newDatasource) || !this.control.control_id) {
        this.getDatasourceColumns(newDatasource).then((data) => {
          this.datasourceBColumns = data;
          // this.control.source_filter_b = "-- Columns: " + JSON.stringify(data) + "\n";
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

    let controlData = this.controlCatalogueById(this.controlId);

    if (!controlData && this.controlId != "new") {
      await this.updateControlCatalogue();
      controlData = this.controlCatalogueById(this.controlId);
    }

    if (controlData) {
      this.control = controlData;
      this.getControlVersions(this.controlId);
      this.getControlLogs(this.control.control_name, this.log_days_back);

      // Force insert instead of update if clone
      if (this.$route.query.clone) {
        delete this.control.control_id;
        this.control.control_name = this.control.control_name + "_CLONE";
      }
      this.startControlLogsRefreshTimer();
      this.initializeControl();
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
    }
  },
  unmounted() {
    this.stopControlLogsRefreshTimer();
  },
};
</script>

<style lang="css" scoped>
.new-day-separator {
  border-top: 2px solid #cfd8dc !important;
}
</style>
