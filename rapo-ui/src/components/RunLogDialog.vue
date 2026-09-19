<template>
  <q-dialog v-model="visible" @hide="stopLive">
    <q-card class="column no-wrap" style="width: 1200px; max-width: 95vw; height: 90vh">
      <q-card-section class="row items-center q-py-sm">
        <div class="text-h6">{{ title }}</div>
        <q-chip v-if="run" class="q-ml-md">
          <q-avatar :icon="runStatus(run.status).icon" :color="runStatus(run.status).color" text-color="white" />
          {{ runStatus(run.status).label }}
        </q-chip>
        <q-space />
        <q-btn flat round icon="close" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section v-if="!run" class="col flex flex-center">
        <q-spinner color="teal" size="3em" />
      </q-card-section>

      <template v-else>
        <q-expansion-item v-model="detailsOpen" dense icon="fas fa-info-circle" label="Run details" header-class="text-weight-bold text-blue-grey-8">
          <div class="q-px-md q-pb-sm scroll" style="max-height: 35vh">
            <div class="details-grid">
              <template v-for="field in details" :key="field.label">
                <div class="text-grey-7">{{ field.label }}</div>
                <div class="text-weight-medium">{{ field.value }}</div>
              </template>
            </div>
            <div v-if="run.text_message" class="q-mt-sm">
              <div class="text-grey-7">Messages</div>
              <pre class="details-pre">{{ run.text_message }}</pre>
            </div>
            <div v-if="run.text_error" class="q-mt-sm">
              <div class="text-deep-orange">Error</div>
              <pre class="details-pre text-deep-orange-9">{{ run.text_error }}</pre>
            </div>
          </div>
        </q-expansion-item>
        <q-separator />

        <div class="row items-center q-px-md q-py-xs q-gutter-sm">
          <q-chip
            v-for="level in levels"
            :key="level.name"
            dense
            clickable
            :outline="!selectedLevels.includes(level.name)"
            :color="level.color"
            text-color="white"
            @click="toggleLevel(level.name)">
            {{ level.name }} <span class="q-ml-xs">({{ levelCounts[level.name] || 0 }})</span>
          </q-chip>
          <q-input v-model="search" dense outlined clearable debounce="300" placeholder="Search log" class="col-3">
            <template v-slot:prepend><q-icon name="search" /></template>
          </q-input>
          <q-space />
          <small class="text-grey-7" v-if="log && log.exists">{{ formatSize(log.size) }}, modified {{ toTimeString(log.modified) }}</small>
          <q-btn flat dense round icon="fas fa-sync" @click="load">
            <q-tooltip>Refresh</q-tooltip>
          </q-btn>
          <q-btn flat dense round icon="fas fa-copy" :disable="!filteredRecords.length" @click="copyLog">
            <q-tooltip>Copy shown lines</q-tooltip>
          </q-btn>
          <q-btn flat dense round icon="fas fa-download" :disable="!log || !log.exists" @click="download">
            <q-tooltip>Download full log file</q-tooltip>
          </q-btn>
        </div>

        <q-banner v-for="notice in notices" :key="notice" dense class="bg-amber-1 text-amber-10 q-mx-md q-mb-xs">
          <template v-slot:avatar><q-icon name="fas fa-exclamation-triangle" color="amber-8" size="xs" /></template>
          {{ notice }}
        </q-banner>

        <div class="col log-body q-mx-md q-mb-md">
          <q-virtual-scroll ref="scroll" class="fit" :items="filteredRecords" :virtual-scroll-item-size="18" v-slot="{ item }">
            <div :key="item.index" class="log-record">
              <span class="text-grey-6">{{ item.time }}</span>
              <span class="log-level" :class="'text-' + levelColor(item.level)">{{ item.level }}</span>
              <span class="text-grey-6 log-thread">{{ item.thread }}</span>
              <span class="log-message">{{ item.message }}</span>
            </div>
          </q-virtual-scroll>
          <div v-if="log && log.exists && !filteredRecords.length" class="absolute-center text-grey-6">No matching lines</div>
        </div>
      </template>
    </q-card>
  </q-dialog>
</template>

<script>
import { Notify } from "quasar";
import { api, notifyError } from "../api";
import { ACTIVE_RUN_STATUSES, runStatus } from "../constants";
import { liveRefetch } from "../socket";
import { copyText, formatNumber, toDateTimeString, toTimeString } from "../utils/format";

const LEVELS = [
  { name: "ERROR", color: "deep-orange" },
  { name: "CRITICAL", color: "red-9" },
  { name: "WARNING", color: "amber-8" },
  { name: "INFO", color: "blue" },
  { name: "DEBUG", color: "blue-grey-4" },
];
// A record starts with "<date time>\t<thread>\t<LEVEL>\t"; other lines continue the previous record (SQL, tracebacks).
const RECORD = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\t([^\t]*)\t([A-Z]+)\t(.*)$/;

function parseLog(text) {
  const records = [];
  for (const line of text.split("\n")) {
    const match = RECORD.exec(line);
    if (match) {
      records.push({ index: records.length, time: match[1], thread: match[2], level: match[3], message: match[4] });
    } else if (records.length) {
      records[records.length - 1].message += "\n" + line;
    } else if (line) {
      records.push({ index: 0, time: "", thread: "", level: "", message: line });
    }
  }
  const last = records[records.length - 1];
  if (last) {
    last.message = last.message.replace(/\n+$/, "");
  }
  return records;
}

// Shows a control run: its rapo_log row and the log file written by its process.
// Open with this.$refs.<ref>.open(run), where run has at least process_id and control_name.
export default {
  data() {
    return {
      visible: false,
      processId: null,
      controlName: "",
      run: null,
      log: null,
      records: [],
      levels: LEVELS,
      selectedLevels: LEVELS.map((level) => level.name),
      search: "",
      detailsOpen: true,
    };
  },
  computed: {
    title() {
      return `${this.controlName} | PID ${this.processId} | Full log`;
    },
    active() {
      return Boolean(this.run && ACTIVE_RUN_STATUSES.includes(this.run.status));
    },
    levelCounts() {
      return this.records.reduce((counts, record) => ({ ...counts, [record.level]: (counts[record.level] || 0) + 1 }), {});
    },
    filteredRecords() {
      const needle = this.search ? this.search.toLowerCase() : null;
      const known = new Set(LEVELS.map((level) => level.name));
      return this.records.filter(
        (record) => (!known.has(record.level) || this.selectedLevels.includes(record.level)) && (!needle || record.message.toLowerCase().includes(needle))
      );
    },
    notices() {
      const notices = [];
      if (!this.log) {
        return notices;
      }
      const runnerHost = this.log.runner ? this.log.runner.split(":")[0] : null;
      if (!this.log.exists) {
        if (runnerHost && runnerHost !== this.log.host) {
          notices.push(`The run was performed on ${this.log.runner}, its log file is on that host: ${this.log.path}`);
        } else {
          notices.push(`Log file not found: ${this.log.path}. It may be deleted by retention, or the run was performed before per-run logs existed.`);
        }
      }
      if (this.log.truncated) {
        notices.push(`The log file has ${this.formatSize(this.log.size)}, only its end is shown. Download it to see everything.`);
      }
      return notices;
    },
    details() {
      const run = this.run;
      const number = (value) => (value == null ? "" : formatNumber(value));
      const level = (value) => (value == null ? "" : formatNumber(value, 2) + "%");
      const fields = [
        ["Control", `${run.control_name || ""} (${run.control_type || ""}, ID ${run.control_id})`],
        ["Status", runStatus(run.status).label],
        ["Added", toDateTimeString(run.added)],
        ["Started", toDateTimeString(run.start_date)],
        ["Ended", toDateTimeString(run.end_date)],
        ["Updated", toDateTimeString(run.updated)],
        ["Date from", toDateTimeString(run.date_from)],
        ["Date to", toDateTimeString(run.date_to)],
        ["Fetched", number(run.fetched_number)],
        ["Success", number(run.success_number)],
        ["Errors", number(run.error_number)],
        ["Error level", level(run.error_level)],
        ["Fetched A / B", [number(run.fetched_number_a), number(run.fetched_number_b)].join(" / ")],
        ["Success A / B", [number(run.success_number_a), number(run.success_number_b)].join(" / ")],
        ["Errors A / B", [number(run.error_number_a), number(run.error_number_b)].join(" / ")],
        ["Error level A / B", [level(run.error_level_a), level(run.error_level_b)].join(" / ")],
        ["Prerequisite value", run.prerequisite_value == null ? "" : String(run.prerequisite_value)],
        ["Performed by", this.log && this.log.runner ? this.log.runner : ""],
      ];
      return fields.filter(([, value]) => value && value.replace(/[ /]/g, "")).map(([label, value]) => ({ label, value }));
    },
  },
  methods: {
    runStatus,
    toTimeString,
    open(run) {
      this.stopLive();
      this.processId = run.process_id;
      this.controlName = run.control_name;
      this.run = null;
      this.log = null;
      this.records = [];
      this.search = "";
      this.detailsOpen = true;
      this.visible = true;
      this.load().then(() => {
        this.stopLiveUpdates = liveRefetch("runs:changed", this.load, { filter: (payload) => (payload.process_ids || []).includes(this.processId), interval: 3000 });
      });
    },
    async load() {
      try {
        const data = await api("get-control-run-log", { params: { process_id: this.processId }, loadingBar: !this.run });
        const followTail = !this.run || this.active;
        this.run = data.run;
        this.log = data.log;
        this.controlName = data.run.control_name || this.controlName;
        this.records = parseLog(data.log.text);
        if (followTail) {
          this.$nextTick(() => this.$refs.scroll && this.$refs.scroll.scrollTo(this.filteredRecords.length - 1));
        }
      } catch (error) {
        notifyError("Failed to load the run log.", error);
      }
    },
    stopLive() {
      if (this.stopLiveUpdates) {
        this.stopLiveUpdates();
        this.stopLiveUpdates = null;
      }
    },
    toggleLevel(name) {
      const index = this.selectedLevels.indexOf(name);
      if (index >= 0) {
        this.selectedLevels.splice(index, 1);
      } else {
        this.selectedLevels.push(name);
      }
    },
    levelColor(name) {
      const level = LEVELS.find((item) => item.name === name);
      return level ? level.color : "grey-7";
    },
    formatSize(bytes) {
      if (bytes == null) {
        return "";
      }
      return bytes < 1024 * 1024 ? `${formatNumber(bytes / 1024, 1)} KB` : `${formatNumber(bytes / 1024 / 1024, 1)} MB`;
    },
    async copyLog() {
      const text = this.filteredRecords.map((record) => [record.time, record.thread, record.level, record.message].join("\t")).join("\n");
      try {
        await copyText(text);
        Notify.create({ type: "positive", message: `${this.filteredRecords.length} log records copied to clipboard` });
      } catch (error) {
        notifyError("Failed to copy the log.", error);
      }
    },
    async download() {
      try {
        const response = await api("download-control-run-log", { params: { process_id: this.processId }, raw: true });
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement("a");
        link.href = url;
        link.download = `${this.controlName}_${this.processId}.log`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      } catch (error) {
        notifyError("Failed to download the log file.", error);
      }
    },
  },
  unmounted() {
    this.stopLive();
  },
};
</script>

<style lang="css" scoped>
.details-grid {
  display: grid;
  grid-template-columns: repeat(4, max-content 1fr);
  column-gap: 12px;
  row-gap: 2px;
  font-size: 13px;
}

.details-pre {
  white-space: pre-wrap;
  font-size: 12px;
  margin: 2px 0 0;
  max-height: 160px;
  overflow: auto;
  background: #f5f7f8;
  padding: 6px;
}

.log-body {
  position: relative;
  border: 1px solid #e0e0e0;
  background: #fafafa;
  min-height: 0;
}

.log-record {
  font-family: Monospace, monospace;
  font-size: 12px;
  line-height: 18px;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 0 8px;
}

.log-level {
  display: inline-block;
  width: 70px;
  margin-left: 8px;
  font-weight: 600;
}

.log-thread {
  display: inline-block;
  min-width: 110px;
  margin-right: 8px;
}
</style>
