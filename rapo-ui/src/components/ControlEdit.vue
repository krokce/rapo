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
      <h2 class="row items-center q-mb-lg">
        <q-chip size="xl" :title="controlType(control.control_type).label">
          <q-avatar :icon="controlType(control.control_type).icon" :color="controlType(control.control_type).color" text-color="white" class="type-avatar" />
          {{ control.control_type }}
        </q-chip>
        &nbsp;
        {{ control.control_name ? control.control_name : "New control" }}
        <q-space />
        <template v-if="control.control_id">
          <run-control-dialog v-if="!dirty" :control_name="control.control_name" :hook="runStarted">
            <q-btn color="primary" icon="fas fa-play" label="Run" />
          </run-control-dialog>
          <span v-else>
            <q-btn color="primary" icon="fas fa-play" label="Run" disable />
            <q-tooltip anchor="bottom right" self="top right" :offset="[0, 5]">Apply your changes first: a run uses the saved configuration</q-tooltip>
          </span>
        </template>
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
          <q-tab v-if="emailEnabled" name="email" label="Email" icon="fas fa-envelope" />
          <q-tab v-if="control.control_id" name="log" label="Run log" icon="fas fa-file-medical-alt" />
        </q-tabs>

        <q-separator />

        <q-form @submit="persist('stay')" @reset="cancel" ref="myForm">
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
                        @click="$refs.versionsDialog.open()"
                        @click.stop.prevent
                        class="cursor-pointer"
                        :class="{ 'text-deep-orange-4': versionChanges.length }">
                        <q-badge rounded size="xs" v-if="versionChanges.length" color="green" floating>{{ versionChanges.length }}</q-badge>
                        <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">Manage versions</q-tooltip>
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

                  <q-select v-if="emailSupported" class="col" outlined emit-value map-options v-model="sendEmail" :options="yesNoOptions" label="Send email">
                    <template v-slot:prepend>
                      <q-icon name="fas fa-envelope" @click.stop.prevent />
                    </template>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      If 'Yes' is selected the results are sent per email when a run finishes. <br />
                      Recipients, condition and attachment are set in the Email tab.
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

                <div v-if="chainNote" class="text-caption text-grey-8">
                  <q-icon name="fas fa-link" class="q-mr-xs" />{{ chainNote }}
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
                      Limit the number of records in the output table. <br />Leave empty or 0 for no limit.
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
                      Limit the number of records in the output table. <br />Leave empty or 0 for no limit.
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
                    <code-box
                      label="Filter"
                      v-model="control.source_filter"
                      :columns="datasourceColumns"
                      :template-vars="true"
                      :hide-chips="filterHiddenChips"
                      :examples="codeExamples.filter"
                      :check="checker('filter', 'source_name')">
                    </code-box>
                  </div>
                  <div class="col" v-if="control.control_type === 'REC' || control.control_type === 'CMP'">
                    <code-box
                      label="Filter (Datasource A)"
                      v-model="control.source_filter_a"
                      :columns="datasourceAColumns"
                      :template-vars="true"
                      :hide-chips="filterHiddenChips"
                      :examples="codeExamples.filter"
                      :check="checker('filter', 'source_name_a')">
                    </code-box>
                  </div>
                  <div class="col" v-if="control.control_type === 'REC' || control.control_type === 'CMP'">
                    <code-box
                      label="Filter (Datasource B)"
                      v-model="control.source_filter_b"
                      :columns="datasourceBColumns"
                      :template-vars="true"
                      :hide-chips="filterHiddenChips"
                      :examples="codeExamples.filter"
                      :check="checker('filter', 'source_name_b')">
                    </code-box>
                  </div>
                </div>

                <div class="row q-my-xs q-gutter-md" v-if="control.control_type == 'ANL'">
                  <div class="col">
                    <code-box
                      label="Mismatch criteria (Error definition)"
                      v-model="control.error_definition"
                      :columns="datasourceColumns"
                      :template-vars="true"
                      :examples="codeExamples.error_definition"
                      :check="checker('error_sql', 'source_name')">
                    </code-box>
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
              </div>
            </q-tab-panel>

            <q-tab-panel name="sql">
              <div class="q-ma-lg q-gutter-y-lg">
                <div class="row q-gutter-md">
                  <div class="col">
                    <code-box
                      label="Preparation SQL"
                      :template-vars="true"
                      :tables="ruleDatasourceTables"
                      v-model="control.preparation_sql"
                      :examples="codeExamples.preparation"
                      :check="checker('preparation')">
                    </code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[-120, -20]">
                      Preparation SQL is executed before the control is started. It can be used to prepare the data for the control. See the enclosed examples.
                    </q-tooltip>
                  </div>
                </div>

                <div class="row q-gutter-md">
                  <div class="col">
                    <code-box
                      label="Prerequisite SQL"
                      :template-vars="true"
                      :tables="ruleDatasourceTables"
                      v-model="control.prerequisite_sql"
                      :examples="codeExamples.prerequisite"
                      :check="checker('prerequisite')">
                    </code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[-120, -20]">
                      Prerequisite SQL is executed before the control is started. If the number returned is 0 the control will be terminated. See the enclosed
                      positive and negative examples.
                    </q-tooltip>
                  </div>
                </div>

                <div class="row q-gutter-md">
                  <div class="col">
                    <code-box
                      label="Completion SQL"
                      :template-vars="true"
                      :tables="ruleDatasourceTables"
                      v-model="control.completion_sql"
                      :examples="codeExamples.completion"
                      :check="checker('completion')">
                    </code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[-120, -20]">
                      Completion SQL is executed after the control is finished. It can be used to clean-up data, log results or execute chain of controls. See
                      the enclosed examples.
                    </q-tooltip>
                  </div>
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
                    <code-box
                      label="Case mapping"
                      v-model="control.case_definition"
                      :columns="datasourceColumns"
                      :examples="codeExamples.case_definition"
                      :check="checker('case_definition', 'source_name')">
                    </code-box>
                    <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                      Use simple SQL case structure to define which discrepancies will be mapped to which Case IDs defined above. See the enclosed example.
                    </q-tooltip>
                  </div>
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
              </div>
            </q-tab-panel>
            <q-tab-panel name="kpi">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="row q-gutter-md">
                  <kpi-config-box class="col" v-model="kpiConfigObject" :control-name="control.control_name" :control-type="control.control_type">
                  </kpi-config-box>
                </div>
              </div>
            </q-tab-panel>
            <q-tab-panel v-if="emailEnabled" name="email">
              <div class="q-ma-lg q-gutter-y-md">
                <email-config-box
                  v-model="ruleConfigObject.email"
                  :control-name="control.control_name"
                  :control-type="control.control_type"
                  :rule-config="control.control_type === 'REC' ? ruleConfigObject : null"
                  :source-columns="emailSourceColumns"
                  :saved="Boolean(control.control_id) && !dirty">
                </email-config-box>
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
                              <q-item dense clickable :disable="dirty" @click="reRun(logRun(log), refreshLogs)" v-close-popup>
                                <q-item-section> Re-run </q-item-section>
                                <q-tooltip v-if="dirty">Apply your changes first: a run uses the saved configuration</q-tooltip>
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
              </div>
            </q-tab-panel>
          </q-tab-panels>

          <div class="editor-actions row items-center q-gutter-sm q-px-lg q-py-sm">
            <q-btn label="Save" color="primary" :loading="saving" @click="persist('close')">
              <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">Save and return to the controls</q-tooltip>
            </q-btn>
            <q-btn label="Apply" color="primary" outline :disable="!dirty || saving" @click="persist('stay')">
              <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">Save and keep editing (Ctrl+S)</q-tooltip>
            </q-btn>
            <q-btn label="Cancel" type="reset" color="primary" flat />
            <q-space />
            <div
              v-if="schemaNotice"
              class="schema-notice text-weight-medium row items-center no-wrap cursor-pointer"
              :class="schemaNotice.class"
              @click="$refs.schemaDialog.open()">
              <q-icon :name="schemaNotice.icon" size="12px" class="q-mr-sm" />
              {{ schemaNotice.label }}
              <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">{{ schemaNotice.tooltip }}</q-tooltip>
            </div>
            <div
              v-if="dirty"
              class="text-orange-9 text-weight-medium row items-center no-wrap"
              :class="{ 'cursor-pointer': savedControlJson !== null }"
              @click="savedControlJson !== null && $refs.controlDiffDialog.open()">
              <q-icon name="fas fa-circle" size="8px" class="q-mr-sm" />
              Unsaved changes
              <q-tooltip v-if="savedControlJson !== null" anchor="top middle" self="bottom middle" :offset="[0, 5]">
                Show what Apply will change
              </q-tooltip>
            </div>
            <template v-if="schemaEnabled && !schemaCheck?.rebuilt_each_run">
              <q-btn v-if="schemaSummary.safe" label="Update schema" color="primary" outline :disable="saving || schemaBusy" @click="applySchema('update')">
                <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Add and widen columns of the result tables, keeping their data</q-tooltip>
              </q-btn>
              <q-btn
                label="Recreate schema"
                color="negative"
                :flat="!schemaRecreateSuggested"
                :unelevated="schemaRecreateSuggested"
                :disable="saving || schemaBusy"
                @click="$refs.schemaDialog.open()">
                <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">
                  Drop the result tables and create them anew: past results are deleted. Shows the tables first.
                </q-tooltip>
              </q-btn>
            </template>
          </div>
        </q-form>
      </q-card>
    </div>

    <run-log-dialog ref="runLogDialog" />
    <schema-diff-dialog
      ref="schemaDialog"
      :check="schemaCheck"
      :dirty="dirty"
      :busy="saving || schemaBusy"
      :exact-rows="schemaExactRows"
      :counting-rows="schemaCountingRows"
      @count="countSchemaRows"
      @drop="dropOrphan"
      @update="applySchema('update')"
      @recreate="(tables) => applySchema('recreate', tables)" />
    <control-diff-dialog ref="controlDiffDialog" :diff="unsavedChanges" :busy="saving" @apply="persist('stay')" />
    <control-versions-dialog
      ref="versionsDialog"
      :current="savedVersionRow"
      :versions="pastVersions"
      :loaded-id="controlVersion && controlVersion.version_id"
      @load="loadVersion"
      @changed="refreshVersions" />
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import { api, notifyError } from "../api";
import { ACTIVE_RUN_STATUSES, CONTROL_ENGINE_OPTIONS, CONTROL_TYPE_OPTIONS, PERIOD_TYPE_OPTIONS, YES_NO_OPTIONS, controlType, controlTypeColor, runStatus } from "../constants";
import { cancelRun, copyResultsSql, copySql, dropTemporaryTables, reRun, revokeRun } from "../runActions";
import { liveRefetch } from "../socket";
import CodeBox from "./CodeBox.vue";
import EditorSkeleton from "./EditorSkeleton.vue";
import RunLogDialog from "./RunLogDialog.vue";
import SchemaDiffDialog from "./SchemaDiffDialog.vue";
import ControlDiffDialog from "./ControlDiffDialog.vue";
import ControlVersionsDialog from "./ControlVersionsDialog.vue";
import RunControlDialog from "./RunControlDialog.vue";
import ScheduleEditBox from "./ScheduleEditBox.vue";
import ReconciliationDiscrepancyCheckboxes from "./ReconciliationDiscrepancyCheckboxes.vue";
import ReconciliationMatchCriteriaBox from "./ReconciliationMatchCriteriaBox.vue";
import ReconciliationMisMatchCriteriaBox from "./ReconciliationMisMatchCriteriaBox.vue";
import CaseConfigBox from "./CaseConfigBox.vue";
import IterationConfigBox from "./IterationConfigBox.vue";
import KpiConfigBox from "./KpiConfigBox.vue";
import EmailConfigBox from "./EmailConfigBox.vue";
import ComparisonCriteriaBox from "./ComparisonCriteriaBox.vue";
import ComparisonOutputTableBox from "./ComparisonOutputTableBox.vue";
import { examplesFor } from "../utils/codeExamples";
import { diffControl, diffKpis } from "../utils/controlDiff";
import { escapeHtml, formatNumber, round, toDateString, toDateTimeString, toTimeString } from "../utils/format";
import { describeOrphan, describeTable, summarizeSchema } from "../utils/schema";
import { defaultSchedule, parseSchedule, scheduleType, serializeSchedule } from "../utils/schedule";
import { allUpstreams, nameIndex, upstreamsOf } from "../utils/chain";
import {
  DEFAULT_SQL_SHEET_NAME,
  EMAIL_CONTROL_TYPES,
  SHEET_NAME_INVALID,
  completeEmailConfig,
  defaultEmailConfig,
  defaultSheetName,
  isEmailAddress,
} from "../utils/email";

// The label of a version in the Version select and the Manage versions dialog.
function versionLabel(version) {
  return "v." + toDateTimeString(version.updated_date ? version.updated_date : version.created_date);
}

export default {
  components: {
    CodeBox,
    EditorSkeleton,
    RunLogDialog,
    RunControlDialog,
    SchemaDiffDialog,
    ControlDiffDialog,
    ControlVersionsDialog,
    ScheduleEditBox,
    ReconciliationDiscrepancyCheckboxes,
    ReconciliationMatchCriteriaBox,
    ReconciliationMisMatchCriteriaBox,
    CaseConfigBox,
    IterationConfigBox,
    KpiConfigBox,
    EmailConfigBox,
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
      // The window variables are still completed in the datasource filters, but get no chip: the date column
      // already limits the fetch to the window.
      filterHiddenChips: ["control_date_from", "control_date_to"],
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
      // The saved state as JSON (buildControlPayload / kpiConfigObject), compared with the form for dirty.
      // null control: never saved (a clone); null KPIs: not loaded yet, not compared.
      savedControlJson: null,
      savedKpiJson: null,
      // True while a control is being loaded, so the datasource watchers don't reset its saved fields.
      initializing: false,
      loadedUpdatedDate: null,
      // The other person's change already notified, so the notice shows once per change.
      noticedUpdatedDate: null,
      controlTypeOptions: CONTROL_TYPE_OPTIONS,
      yesNoOptions: YES_NO_OPTIONS,
      periodTypeOptions: PERIOD_TYPE_OPTIONS,
      activeRunStatuses: ACTIVE_RUN_STATUSES,
      // The answer of check-control-schema for the form as it is, null until the first one.
      schemaCheck: null,
      schemaBusy: false,
      // Exact row counts asked for in SchemaDiffDialog ({table: {rows, counted}}), and the tables being counted.
      schemaExactRows: {},
      schemaCountingRows: {},
    };
  },
  created() {
    // Pending/finished get-datasource-columns requests by datasource name (see getDatasourceColumns).
    this.columnRequests = {};
    window.addEventListener("keydown", this.onKeydown);
    window.addEventListener("beforeunload", this.onBeforeUnload);
  },
  computed: {
    // The Example menus of the code boxes, for this control's type and name.
    codeExamples() {
      const context = { controlType: this.control.control_type, controlName: this.control.control_name };
      const fields = ["filter", "error_definition", "case_definition", "preparation", "prerequisite", "completion"];
      return Object.fromEntries(fields.map((field) => [field, examplesFor({ ...context, field })]));
    },
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
    ...mapState(["controlCatalogue"]),
    // A datasource that is the result table of another control makes this a chain-rule (utils/chain.js):
    // said under the datasources, from the form as it is, with every control a run would perform first.
    chainNote() {
      const others = this.controlCatalogue.filter((row) => row.control_id !== this.control.control_id && row.control_name !== this.control.control_name);
      const catalogue = [...others, this.control];
      const direct = upstreamsOf(this.control, nameIndex(catalogue));
      if (!direct.length) {
        return "";
      }
      const sources = direct.map((item) => `${item.side ? `Datasource ${item.side.toUpperCase()}` : "The datasource"} is the result table of ${item.control_name}`).join("; ");
      const upstream = allUpstreams(this.control.control_name, catalogue);
      return `${sources}. A run first runs ${upstream.join(", ")} for the same period and reads only the records of those runs, so no date window is applied to ${direct.length > 1 ? "these datasources" : "it"}.`;
    },
    pastVersions() {
      return this.controlVersions.slice(1);
    },
    // The saved row for the Manage versions dialog, from the catalogue rather than the form.
    savedVersionRow() {
      const row = this.control.control_id && this.controlCatalogueById(this.control.control_id);
      return row ? { ...row, label: versionLabel(row) } : null;
    },
    // Whether the form differs from the saved control, so Apply has something to write.
    dirty() {
      if (!this.ready) {
        return false;
      }
      if (this.savedControlJson === null) {
        return true;
      }
      if (JSON.stringify(this.buildControlPayload()) !== this.savedControlJson) {
        return true;
      }
      return this.savedKpiJson !== null && JSON.stringify(this.kpiConfigObject) !== this.savedKpiJson;
    },
    // The email lives in rule_config, which CMP keeps as a list, so CMP has none.
    emailSupported() {
      return EMAIL_CONTROL_TYPES.includes(this.control.control_type);
    },
    emailEnabled() {
      return this.emailSupported && Boolean(this.ruleConfigObject && this.ruleConfigObject.email && this.ruleConfigObject.email.enabled);
    },
    // Switching it off keeps the rest of the configuration, so switching it back on restores it.
    sendEmail: {
      get() {
        return this.emailEnabled ? "Y" : "N";
      },
      set(value) {
        if (!this.ruleConfigObject.email) {
          this.ruleConfigObject.email = defaultEmailConfig(this.control.control_type);
        }
        this.ruleConfigObject.email.enabled = value === "Y";
      },
    },
    // Source columns per attachment sheet, offered while the result table does not exist yet.
    emailSourceColumns() {
      if (this.singleSource) {
        return { main: this.control.output_table_columns || this.datasourceColumns || [] };
      }
      return { a: this.control.output_table_a_columns || this.datasourceAColumns || [], b: this.control.output_table_b_columns || this.datasourceBColumns || [] };
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
    // A saved control has result tables to compare; a new one or a clone gets them on its first run.
    schemaEnabled() {
      return this.ready && Boolean(this.control.control_id) && !this.$route.query.clone;
    },
    // The fields the result table schema depends on, as they would be saved. A change re-checks it.
    schemaKey() {
      if (!this.schemaEnabled) {
        return null;
      }
      const payload = this.buildControlPayload();
      const fields = ["control_name", "control_type", "with_drop", "need_a", "need_b", "source_name", "source_date_field", "output_table"];
      const sides = ["source_name", "source_date_field", "source_key_field", "output_table"];
      const keys = [...fields, ...sides.flatMap((field) => [field + "_a", field + "_b"])];
      return JSON.stringify([...keys.map((key) => payload[key] ?? null), payload.control_type === "REC" ? payload.rule_config : null]);
    },
    schemaSummary() {
      return summarizeSchema(this.schemaCheck);
    },
    // A new datasource or a column Update schema cannot convert: starting the tables anew is the better fix.
    schemaRecreateSuggested() {
      return this.schemaSummary.incompatible > 0 || Boolean(this.schemaCheck && this.schemaCheck.source_changed.length);
    },
    // The footer marker beside "Unsaved changes", which opens the details. None while the schema matches.
    schemaNotice() {
      const check = this.schemaCheck;
      const summary = this.schemaSummary;
      if (!this.schemaEnabled || !check) {
        return null;
      }
      const orphans = summary.orphans.map((orphan) => orphan.table.toUpperCase()).join(", ");
      const orphaned = { label: "Orphaned tables", icon: "fas fa-trash-alt", class: "text-negative", tooltip: `No run writes ${orphans} any more. Click to review and drop.` };
      if (check.rebuilt_each_run) {
        if (summary.orphans.length) {
          return orphaned;
        }
        return { label: "Rebuilt on every run", icon: "fas fa-sync-alt", class: "text-grey-7", tooltip: "The result tables are dropped on each run, so their schema always follows the configuration." };
      }
      if (summary.level === "error") {
        return { label: "Schema check failed", icon: "fas fa-exclamation-triangle", class: "text-negative", tooltip: summary.errors.join(" ") };
      }
      if (summary.level === "recreate") {
        return { label: "Schema needs recreate", icon: "fas fa-exclamation-circle", class: "text-negative", tooltip: `${summary.incompatible} column(s) cannot be converted in place. Click for details.` };
      }
      if (summary.level === "orphaned") {
        return orphaned;
      }
      if (summary.level === "update") {
        const source = check.source_changed.length ? "Datasource changed: " : "";
        return { label: "Schema changes", icon: "fas fa-circle", class: "text-amber-9", tooltip: `${source}${summary.safe} column change(s) for the result tables. Click for details.` };
      }
      if (check.source_changed.length) {
        return { label: "Datasource changed", icon: "fas fa-circle", class: "text-amber-9", tooltip: "The result tables fit the new datasource. Recreate schema starts them anew. Click for details." };
      }
      if (summary.renamed) {
        return { label: "Tables will be renamed", icon: "fas fa-circle", class: "text-blue-grey-7", tooltip: "Saving renames the result tables to the new control name." };
      }
      return null;
    },
    // Indexes of run log rows added on another day than the previous row, drawn with a separator line.
    newDayLogRows() {
      const logs = this.controlLogs;
      return new Set(logs.map((log, index) => index).filter((index) => index > 0 && toDateString(logs[index - 1].added) !== toDateString(logs[index].added)));
    },
  },
  methods: {
    // The Check of a code box: validate-sql parses the text against the unsaved form (datasource, name, case
    // IDs), so a statement can be checked before it is saved.
    checker(kind, sourceField) {
      return (statement) =>
        api("validate-sql", {
          method: "POST",
          loadingBar: false,
          body: {
            kind,
            statement,
            control_name: this.control.control_name,
            control_type: this.control.control_type,
            source_name: sourceField ? this.control[sourceField] : null,
            case_ids: this.caseConfigObject.map((item) => item.case_id),
          },
        });
    },
    ...mapActions(["updateControlCatalogue", "updateKpiTypes"]),
    updateLogDaysBack() {
      return this.refreshLogs();
    },
    controlType,
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
      this.savedKpiJson = null;
      if (!this.kpiAvailable || !controlName) {
        return;
      }
      try {
        this.kpiConfigObject = await api("get-control-kpis", { params: { control_name: controlName }, loadingBar: false });
      } catch (error) {
        notifyError("KPI configuration was not loaded.", error);
      }
      // Not versioned, so these rows are the saved state whichever version is shown.
      this.savedKpiJson = JSON.stringify(this.kpiConfigObject);
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
        this.ruleConfigObject = {};
      }
    },
    async getControlVersions(controlId) {
      try {
        const versions = await this.fetchVersions(controlId);
        this.control.label = versionLabel(this.control);
        // A copy: the form is edited in place, and the saved entry must not follow it.
        this.controlVersions = [JSON.parse(JSON.stringify(this.control)), ...versions];
        this.controlVersion = this.controlVersions[0];
      } catch (error) {
        notifyError("Failed to load control versions.", error);
      }
    },
    async fetchVersions(controlId) {
      const versions = await api("get-control-versions", { params: { control_id: controlId } });
      versions.forEach((version) => (version.label = versionLabel(version)));
      return versions;
    },
    // After versions were deleted: the list follows, the form stays as it is.
    async refreshVersions() {
      try {
        const versions = await this.fetchVersions(this.control.control_id);
        const loadedId = this.controlVersion && this.controlVersion.version_id;
        this.controlVersions = [this.controlVersions[0], ...versions];
        this.controlVersion = versions.find((version) => version.version_id === loadedId) || this.controlVersions[0];
      } catch (error) {
        notifyError("Failed to load control versions.", error);
      }
    },
    // From the Manage versions dialog, the same as picking it in the Version select.
    loadVersion(version) {
      this.controlVersion = version;
      this.controlVersionChanged();
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
          // ANL and REP keep only the email in rule_config.
          this.ruleConfigObject = ruleConfig && !Array.isArray(ruleConfig) ? ruleConfig : {};
        }
        if (this.ruleConfigObject.email && this.emailSupported) {
          completeEmailConfig(this.ruleConfigObject.email, this.control.control_type);
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
    // A past version takes the saved row's ID and stamps and leaves its audit columns, so that the form holds only
    // its configuration: one equal to the saved control is not dirty, and Apply writes no old stamps back.
    controlVersionChanged() {
      const saved = this.controlVersions[0];
      const version = this.controlVersion;
      if (version === saved) {
        this.versionChanges = [];
        this.loadControl(saved);
        return;
      }
      const data = { ...version };
      for (const key of ["audit_action", "audit_user", "audit_date", "version_id"]) {
        delete data[key];
      }
      for (const key of ["control_id", "created_by", "created_date", "updated_by", "updated_date"]) {
        data[key] = saved[key];
      }
      // Against the raw saved row: the form carries keys of its own (e.g. output_table_columns).
      this.versionChanges = diffControl(JSON.stringify(this.savedVersionRow || saved), version);
      this.loadControl(data);
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
    // The rapo_config row as it would be saved, built from the form without touching it, so that it can also be
    // compared with the saved state (dirty). kpi_config is kept apart, since the KPIs load separately.
    // What Apply would change against the saved state (ControlDiffDialog). Saved controls only: a new control or
    // a clone has no saved state to compare with.
    unsavedChanges() {
      return [...diffControl(this.savedControlJson, this.buildControlPayload()), ...diffKpis(this.savedKpiJson, this.kpiConfigObject)];
    },
    buildControlPayload() {
      const control = { ...this.control };
      // Set by getControlVersions for the version selector only.
      delete control.label;
      // Add new line if last line contains a comment to avoid RAPO SQL builder issue
      control.source_filter = this.addNewLineIfLastLineStartsWithDoubleDash(control.source_filter);
      control.source_filter_a = this.addNewLineIfLastLineStartsWithDoubleDash(control.source_filter_a);
      control.source_filter_b = this.addNewLineIfLastLineStartsWithDoubleDash(control.source_filter_b);

      control.schedule_config = serializeSchedule(this.scheduleObject);

      // ANL rule
      if (control.control_type === "ANL") {
        if (!control.output_table_columns) {
          control.output_table = null;
        } else {
          control.output_table = JSON.stringify({
            columns: control.output_table_columns,
          });
        }

        if (this.caseConfigObject.length > 0) {
          control.case_config = JSON.stringify(this.caseConfigObject);
        } else {
          control.case_config = null;
        }
      }

      // ANL and REP keep only the email in rule_config.
      if (control.control_type === "ANL" || control.control_type === "REP") {
        control.rule_config = Object.keys(this.ruleConfigObject || {}).length ? JSON.stringify(this.ruleConfigObject) : null;
      }

      // REP rule
      if (control.control_type === "REP") {
        if (!control.output_table_columns) {
          control.output_table = null;
        } else {
          control.output_table = JSON.stringify({
            columns: control.output_table_columns,
          });
        }
      }

      // REC rule
      if (control.control_type === "REC") {
        // output limit should not be used for REC rules - instead use output_limit_a and output_limit_b in rule_config
        control.output_limit = null;

        if (!control.output_table_a_columns) {
          control.output_table_a = null;
        } else {
          control.output_table_a = JSON.stringify({
            columns: control.output_table_a_columns,
          });
        }

        if (!control.output_table_b_columns) {
          control.output_table_b = null;
        } else {
          control.output_table_b = JSON.stringify({
            columns: control.output_table_b_columns,
          });
        }

        if (this.ruleConfigObject.need_issues_a || this.ruleConfigObject.need_recons_a) {
          control.need_a = "Y";
        } else {
          control.need_a = "N";
        }

        if (this.ruleConfigObject.need_issues_b || this.ruleConfigObject.need_recons_b) {
          control.need_b = "Y";
        } else {
          control.need_b = "N";
        }

        if (!control.source_key_field_a) {
          control.source_key_field_a = "TAG";
        }
        if (!control.source_key_field_b) {
          control.source_key_field_b = "TAG";
        }

        control.rule_config = JSON.stringify(this.ruleConfigObject);
      }

      // CMP rule
      if (control.control_type === "CMP") {
        control.output_table_a = null;
        control.output_table_b = null;

        control.output_table = JSON.stringify({
          columns: this.normalizeOutputColumns(this.cmpOutputTable),
        });

        control.error_definition = JSON.stringify(this.ruleErrorObject);

        control.rule_config = JSON.stringify(this.ruleConfigObject);

        if (this.caseConfigObject.length > 0) {
          control.case_config = JSON.stringify(this.caseConfigObject);
        } else {
          control.case_config = null;
        }
      }

      if (this.iterationConfigObject.length > 0) {
        control.iteration_config = JSON.stringify(this.iterationConfigObject);
      } else {
        control.iteration_config = null;
      }

      return control;
    },
    // The KPIs travel beside the control's own columns. The key is left out entirely when there are no KPI tables,
    // which tells the server not to touch them.
    buildPayload() {
      const body = this.buildControlPayload();
      if (this.kpiAvailable) {
        body.kpi_config = this.kpiConfigObject;
      }
      return body;
    },
    // The first problem of an enabled email configuration, or null.
    emailConfigError() {
      const email = this.ruleConfigObject.email;
      const recipients = [...email.to, ...email.cc, ...email.bcc];
      if (!email.to.length) {
        return "Please enter at least one email recipient (To).";
      }
      const invalid = recipients.filter((address) => !isEmailAddress(address));
      if (invalid.length) {
        return "Not an email address: " + invalid.join(", ");
      }
      if (!email.subject || !email.subject.trim()) {
        return "Please enter an email subject.";
      }
      if (email.max_records != null && !(Number.isInteger(email.max_records) && email.max_records > 0)) {
        return "Max records must be a whole number greater than 0.";
      }
      const resultKeys = this.control.control_type === "REC" ? ["a", "b"] : ["main"];
      const sheetKeys = [...resultKeys, "sql"].filter((key) => email.sheets[key].enabled);
      if (email.sheets.sql.enabled && !(email.sheets.sql.query || "").trim()) {
        return "Please enter the query of the Free SQL sheet, or turn its Include off.";
      }
      const invalidName = sheetKeys.map((key) => email.sheets[key].name).find((name) => name && SHEET_NAME_INVALID.test(name));
      if (invalidName) {
        return "Sheet name '" + invalidName + "' contains a character Excel does not allow: [ ] : * ? / \\";
      }
      const defaultName = (key) => (key === "sql" ? DEFAULT_SQL_SHEET_NAME : defaultSheetName(key, this.control.control_name));
      const sheetNames = sheetKeys.map((key) => (email.sheets[key].name || defaultName(key)).trim().toLowerCase());
      if (new Set(sheetNames).size < sheetNames.length) {
        return "The sheets of the email need different names.";
      }
      if (this.control.control_type === "REC") {
        const sides = ["a", "b"].filter((side) => email.sheets[side].enabled);
        const available = (side) => [
          ...(this.ruleConfigObject["need_issues_" + side] ? ["Loss", "Discrepancy"] : []),
          ...(this.ruleConfigObject["need_recons_" + side] ? ["Match"] : []),
        ];
        const empty = sides.find((side) => available(side).length && !email.sheets[side].result_types.some((type) => available(side).includes(type)));
        if (empty) {
          return "Please choose at least one result type for sheet " + empty.toUpperCase() + ", or turn its Include off.";
        }
      }
      return null;
    },
    isBlank(value) {
      // Number inputs give "" when cleared; 0 is a valid value.
      return value == null || value === "";
    },
    // Checks the form, and on a problem notifies and jumps to the tab where it is. Returns whether it may be saved.
    validate() {
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

      if (!errorTab && this.emailEnabled) {
        const emailError = this.emailConfigError();
        if (emailError) {
          this.$q.notify({ type: "negative", message: emailError });
          errorTab = "email";
        }
      }

      if (!errorTab && (this.isBlank(this.control.period_back) || this.isBlank(this.control.period_number))) {
        this.$q.notify({
          type: "negative",
          message: "Please enter a period back and number of periods.",
        });
        errorTab = "scheduler";
      }

      if (errorTab) {
        this.tab = errorTab;
      }
      return !errorTab;
    },
    // Save ("close": back to the list) or Apply ("stay"). A form without changes is not written at all, so no
    // version is added to rapo_config_bak.
    async persist(mode) {
      if (this.saving) {
        return;
      }
      if (!this.dirty) {
        this.$q.notify({ color: "grey-7", message: "No changes" });
        if (mode === "close") {
          this.$router.push({ name: "controls" });
        }
        return;
      }
      if (this.validate()) {
        await this.submit(mode, true);
      }
    },
    // With lock, the server refuses (409) to overwrite a row changed since it was loaded here.
    async submit(mode, lock) {
      const body = this.buildPayload();
      if (lock && this.control.control_id && this.loadedUpdatedDate) {
        body.expected_updated_date = this.loadedUpdatedDate;
      }
      this.saving = true;
      let result;
      try {
        result = await api("save-control", { method: "POST", body });
      } catch (error) {
        if (error.status === 409) {
          this.saving = false;
          this.resolveConflict(mode, error.message);
          return false;
        }
        // The control row is written, only its KPIs are not: take the row as saved, leave the KPIs changed.
        if (error.message.startsWith("Control was saved")) {
          await this.afterSave({}, false);
        }
        // stay on the page so unsaved edits are not lost
        this.saving = false;
        notifyError("Control was not saved.", error);
        return false;
      }
      // The controls reading this one's results follow a rename (chain-rules).
      if (result.renamed_dependents && result.renamed_dependents.length) {
        this.$q.notify({ message: `The datasources of ${result.renamed_dependents.join(", ")} now read the renamed result tables.` });
      }
      if (mode === "close") {
        this.savedControlJson = JSON.stringify(this.buildControlPayload());
        this.savedKpiJson = null;
        this.saving = false;
        this.$q.notify({ type: "positive", message: "Control: " + this.control.control_name + " was saved successfully." });
        this.$router.push({ name: "controls" });
        return true;
      }
      await this.afterSave(result, true);
      this.saving = false;
      this.$q.notify({ type: "positive", message: "Control: " + this.control.control_name + " was saved." });
      this.checkSchema();
      return true;
    },
    // Takes the saved row's ID and stamps into the form (an insert has none yet, and the next save needs them),
    // re-takes the saved state and, for a control saved for the first time, moves to its own URL.
    async afterSave(result, withKpis) {
      const firstSave = !this.control.control_id || this.$route.query.clone;
      try {
        await this.updateControlCatalogue();
      } catch (error) {
        notifyError("Failed to reload controls.", error);
      }
      const saved = this.controlCatalogueById(result.control_id || this.control.control_id) || this.controlCatalogue.find((row) => row.control_name === this.control.control_name);
      if (saved) {
        for (const key of ["control_id", "created_by", "created_date", "updated_by", "updated_date"]) {
          this.control[key] = saved[key];
        }
      }
      this.loadedUpdatedDate = this.control.updated_date;
      this.savedControlJson = JSON.stringify(this.buildControlPayload());
      if (withKpis) {
        this.savedKpiJson = JSON.stringify(this.kpiConfigObject);
      }
      this.versionChanges = [];
      if (!this.control.control_id) {
        return;
      }
      this.getControlVersions(this.control.control_id);
      if (firstSave) {
        await this.$router.replace({ name: "edit-control", params: { controlId: String(this.control.control_id) } });
        this.getControlLogs(this.control.control_name, this.log_days_back);
        if (!this.stopLiveUpdates) {
          this.startLiveUpdates();
        }
      }
    },
    resolveConflict(mode, message) {
      this.$q
        .dialog({
          title: "Control changed meanwhile",
          message: `${message} Overwrite it with your version, or reload it and lose your changes?`,
          cancel: { label: "Keep editing", flat: true },
          persistent: true,
          options: {
            type: "radio",
            model: "reload",
            items: [
              { label: "Reload the saved version (discard my changes)", value: "reload" },
              { label: "Overwrite it with my version", value: "overwrite" },
            ],
          },
        })
        .onOk(async (choice) => {
          if (choice === "overwrite") {
            await this.submit(mode, false);
            return;
          }
          try {
            await this.updateControlCatalogue();
          } catch (error) {
            notifyError("Failed to reload controls.", error);
            return;
          }
          const latest = this.controlCatalogueById(this.control.control_id);
          if (latest) {
            this.reloadControl(latest);
          }
        });
    },
    cancel() {
      // The route guard asks first when there are unsaved changes.
      this.$router.push({ name: "controls" });
    },
    // Ctrl+S / Cmd+S is Apply anywhere in the editor, and never the browser's "Save page as".
    onKeydown(event) {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && (event.key === "s" || event.key === "S")) {
        event.preventDefault();
        if (this.ready) {
          this.persist("stay");
        }
      }
    },
    onBeforeUnload(event) {
      if (this.dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    },
    // After a run started from the header: its progress shows in the run log.
    runStarted() {
      this.tab = "log";
      this.refreshLogs();
    },
    // Compares the result tables with the schema the form would create (debounced), for the footer marker.
    // An answer overtaken by a later request is dropped.
    checkSchema(delay = 0) {
      clearTimeout(this.schemaTimer);
      if (!this.schemaEnabled) {
        this.schemaCheck = null;
        return;
      }
      this.schemaTimer = setTimeout(async () => {
        const request = (this.schemaRequest = (this.schemaRequest || 0) + 1);
        try {
          const check = await api("check-control-schema", { method: "POST", body: this.buildControlPayload(), loadingBar: false });
          if (request === this.schemaRequest) {
            this.schemaCheck = check;
          }
        } catch (error) {
          if (request === this.schemaRequest) {
            this.schemaCheck = { source_changed: [], tables: [], error: error.message };
          }
        }
      }, delay);
    },
    // A count(*) scans the whole table, so it runs only on request. The table belongs to the saved control, which
    // is still under its old name while a rename is unsaved.
    async countSchemaRows(table) {
      const name = this.schemaCheck.renamed_from || this.schemaCheck.control_name;
      this.schemaCountingRows = { ...this.schemaCountingRows, [table]: true };
      try {
        const result = await api("count-control-table-rows", { params: { name, table } });
        this.schemaExactRows = { ...this.schemaExactRows, [table]: result };
      } catch (error) {
        notifyError("Counting the rows of " + table.toUpperCase() + " failed.", error);
      } finally {
        this.schemaCountingRows = { ...this.schemaCountingRows, [table]: false };
      }
    },
    // Drops a result table runs no longer write. The server checks it against the saved configuration, so unsaved
    // changes (e.g. the unticked output that orphaned it) are saved first.
    dropOrphan(table) {
      const orphan = this.schemaSummary.orphans.find((item) => item.table === table);
      const lines = [];
      if (this.dirty) {
        lines.push("Your unsaved changes are saved first.");
      }
      lines.push(describeOrphan(orphan, this.schemaExactRows[table]));
      this.$q
        .dialog({
          title: "Drop orphaned table?",
          message: lines.map((line) => `<div class="q-mb-xs">${escapeHtml(line)}</div>`).join("") + '<div class="text-negative q-mt-md">Its past results will be deleted!</div>',
          html: true,
          ok: { label: "Drop", color: "negative" },
          cancel: { label: "Cancel", flat: true },
          persistent: true,
        })
        .onOk(async () => {
          if (this.dirty) {
            if (!this.validate() || !(await this.submit("stay", true))) {
              return;
            }
          }
          this.schemaBusy = true;
          try {
            await api("drop-orphaned-table", { method: "POST", params: { table } });
            this.$q.notify({ type: "positive", message: table.toUpperCase() + " was dropped." });
          } catch (error) {
            notifyError("Dropping " + table.toUpperCase() + " failed.", error);
          } finally {
            this.schemaBusy = false;
            this.checkSchema();
          }
        });
    },
    // Update schema (add, widen, make nullable) or Recreate schema (drop and create now). A run reads the saved
    // configuration, so unsaved changes are saved first, and the tables never get ahead of the saved row.
    // Recreate takes the tables to recreate (target names, i.e. after a pending rename), from SchemaDiffDialog.
    applySchema(action, tables = null) {
      const check = this.schemaCheck;
      const summary = this.schemaSummary;
      const lines = [];
      if (this.dirty) {
        lines.push("Your unsaved changes are saved first.");
      }
      const affected = action === "recreate" ? summary.tables.filter((table) => tables.includes(table.target)) : summary.tables;
      for (const table of affected) {
        lines.push(describeTable(table, action, this.schemaExactRows[table.table]));
      }
      if (action === "update" && summary.incompatible) {
        lines.push("Incompatible columns stay as they are, runs fail until the schema is recreated.");
      }
      if (check && check.active_run) {
        lines.push("A run of this control is in progress and may fail.");
      }
      const recreate = action === "recreate";
      this.$q
        .dialog({
          title: recreate ? "Recreate result tables?" : "Update result tables?",
          message: lines.map((line) => `<div class="q-mb-xs">${escapeHtml(line)}</div>`).join("") + (recreate ? '<div class="text-negative q-mt-md">Past results will be deleted!</div>' : ""),
          html: true,
          ok: { label: recreate ? "Recreate" : "Update", color: recreate ? "negative" : "primary" },
          cancel: { label: "Cancel", flat: true },
          persistent: true,
        })
        .onOk(async () => {
          if (this.dirty) {
            if (!this.validate() || !(await this.submit("stay", true))) {
              return;
            }
          }
          const name = this.control.control_name;
          this.schemaBusy = true;
          try {
            const params = recreate ? { name, tables: tables.join(",") } : { name };
            const result = await api(recreate ? "recreate-control-schema" : "update-control-schema", { method: "POST", params });
            if (recreate) {
              this.$q.notify({ type: "positive", message: tables.join(", ").toUpperCase() + " recreated." });
            } else if (result.incompatible && result.incompatible.length) {
              this.$q.notify({ type: "warning", message: "Result tables of " + name + " were updated, except: " + result.incompatible.join(", ").toUpperCase() + ". Recreate the schema to fix them." });
            } else {
              this.$q.notify({ type: "positive", message: "Result tables of " + name + " were updated." });
            }
          } catch (error) {
            notifyError((recreate ? "Recreating" : "Updating") + " the result tables of " + name + " failed.", error);
          } finally {
            this.schemaBusy = false;
            this.schemaExactRows = {};
            this.checkSchema();
          }
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
      const stopLogs = liveRefetch("runs:changed", this.onRunsChanged, {
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
    // A run may have created or updated the result tables, so a notice about them is re-checked.
    onRunsChanged() {
      this.updateLogDaysBack();
      if (this.schemaNotice && !this.schemaCheck.rebuilt_each_run) {
        this.checkSchema(2000);
      }
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
      if (latest.updated_date === this.loadedUpdatedDate || latest.updated_date === this.noticedUpdatedDate) {
        return;
      }
      // Noticed once. loadedUpdatedDate stays what the form is based on, so a save still meets the lock (409).
      this.noticedUpdatedDate = latest.updated_date;
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
    async reloadControl(latest) {
      this.versionChanges = [];
      await this.loadControl(latest);
      this.loadedUpdatedDate = latest.updated_date;
      this.savedControlJson = JSON.stringify(this.buildControlPayload());
      this.getControlVersions(this.control.control_id);
    },
  },
  watch: {
    schemaKey(key, previous) {
      if (key !== previous) {
        this.checkSchema(previous === null ? 0 : 800);
      }
    },
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
      // A clone has never been saved, so it stays dirty (null) until it is.
      if (!this.$route.query.clone) {
        this.savedControlJson = JSON.stringify(this.buildControlPayload());
      }
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
      await this.$nextTick();
      this.savedControlJson = JSON.stringify(this.buildControlPayload());
    }
  },
  unmounted() {
    window.removeEventListener("keydown", this.onKeydown);
    window.removeEventListener("beforeunload", this.onBeforeUnload);
    clearTimeout(this.schemaTimer);
    if (this.stopLiveUpdates) {
      this.stopLiveUpdates();
    }
  },
  // Leaving with unsaved changes (Cancel, the side menu, back) asks first.
  beforeRouteLeave(to, from, next) {
    if (!this.dirty || this.saving) {
      next();
      return;
    }
    this.$q
      .dialog({ title: "Unsaved changes", message: "Discard your unsaved changes?", ok: { label: "Discard", color: "negative" }, cancel: { label: "Keep editing", flat: true }, persistent: true })
      .onOk(() => {
        this.$q.notify({ type: "warning", message: "Changes discarded" });
        next();
      })
      .onCancel(() => next(false));
  },
};
</script>

<style lang="css" scoped>
/* A chip rounds its avatar with a fixed radius, which is not a circle at size xl. */
.q-chip .type-avatar {
  border-radius: 50%;
}

/* Save / Apply / Cancel stay in view on every tab, at the bottom of the window while the card is longer. */
.editor-actions {
  position: sticky;
  bottom: 0;
  z-index: 2;
  background: white;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
}

.schema-notice:hover {
  text-decoration: underline;
}

.new-day-separator > td {
  border-top: 2px solid #cfd8dc !important;
}
</style>
