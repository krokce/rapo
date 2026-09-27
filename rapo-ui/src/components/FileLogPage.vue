<template>
  <q-page>
    <file-log-table
      :datasource-id="Number(id)"
      :initial-day="$route.query.date || null"
      :highlight-id="$route.query.file ? Number($route.query.file) : null"
      :tables="datasource ? datasource.tables : []"
      selectable
      max-height="calc(100vh - 330px)"
      @day="dayChanged"
      @loaded="(files) => (loggedName = files.length ? files[0].sourcename : loggedName)">
      <template #title>
        <div class="row items-center no-wrap">
          <q-chip v-if="datasource" size="xl" :title="lane(datasource.isactive).label">
            <q-avatar :icon="lane(datasource.isactive).icon" :color="lane(datasource.isactive).color" text-color="white" class="type-avatar" />
            <span class="text-weight-bold">{{ lane(datasource.isactive).short }}</span>
          </q-chip>
          <span class="q-ml-sm">{{ datasource ? datasource.sourcename : loggedName || `Datasource ${id}` }}</span>
        </div>
      </template>
      <template #after-day>
        <div v-if="!datasource && loggedName" class="row items-center">
          <q-chip color="orange-2" text-color="orange-10" icon="fas fa-exclamation-triangle" class="title-chip">
            No configuration
            <q-tooltip>The file log names this datasource, but PDI_CORE_DS_CONFIG has no row of ID {{ id }} any more.</q-tooltip>
          </q-chip>
        </div>
        <div v-if="datasource && loggedName && loggedName !== datasource.sourcename" class="row items-center">
          <q-chip color="orange-2" text-color="orange-10" icon="fas fa-not-equal" class="title-chip">
            Log says {{ loggedName }}
            <q-tooltip max-width="400px">
              The file log names SOURCEID {{ id }} {{ loggedName }}, not {{ datasource.sourcename }}: these files may belong to another datasource (an ID
              reused, or the configuration copied from another environment).
            </q-tooltip>
          </q-chip>
        </div>
        <div class="row items-center">
          <q-btn flat round color="primary" icon="fas fa-arrow-left" :to="{ name: 'files', query: dayQuery }">
            <q-tooltip>Back to the Files of the day</q-tooltip>
          </q-btn>
          <q-btn v-if="datasource" flat round color="primary" :icon="datasourceIcon" :to="{ name: 'edit-datasource', params: { id } }">
            <q-tooltip>Edit the datasource</q-tooltip>
          </q-btn>
        </div>
      </template>
    </file-log-table>
  </q-page>
</template>

<script>
import { mapActions, mapState } from "vuex";
import FileLogTable from "./FileLogTable.vue";
import { DATASOURCE_ICON, datasourceLane } from "../constants";

// The files of one datasource on one day (/files-log/<id>?date=YYYY-MM-DD&file=<id>), opened from the Files page: the
// File log of the datasource editor, with files to pick and recycle, reload or delete.
export default {
  name: "FileLogPage",
  components: { FileLogTable },
  props: ["id"],
  data() {
    // loggedName: the name the file log gives the datasource, for one whose configuration is gone.
    return { datasourceIcon: DATASOURCE_ICON, loggedName: null };
  },
  computed: {
    ...mapState(["datasourceCatalogue"]),
    datasource() {
      return this.datasourceCatalogue.find((row) => row.id === Number(this.id)) || null;
    },
    dayQuery() {
      return this.$route.query.date ? { date: this.$route.query.date } : {};
    },
  },
  methods: {
    ...mapActions(["updateDatasourceCatalogue"]),
    lane: datasourceLane,
    // The day the table moved to goes into the URL, so a reload or Back keeps it; the highlighted file stays with its day.
    dayChanged(day) {
      if ((day || null) === (this.$route.query.date || null)) {
        return;
      }
      const query = day ? { date: day } : {};
      this.$router.replace({ name: "files-log", params: { id: this.id }, query });
    },
  },
  mounted() {
    if (!this.datasource) {
      this.updateDatasourceCatalogue().catch(() => null);
    }
  },
};
</script>

<style scoped>
/* A chip rounds its avatar with a fixed radius, which is not a circle at size xl. */
.q-chip .type-avatar {
  border-radius: 50%;
}

/* Beside the h2 title, whose size and light weight it would inherit. */
.title-chip {
  font-size: 14px;
  font-weight: 500;
}
</style>
