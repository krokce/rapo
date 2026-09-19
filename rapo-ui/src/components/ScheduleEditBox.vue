<template>
  <div>
    <div class="row q-gutter-md">
      <q-select
        class="col"
        outlined
        emit-value
        map-options
        v-model="scheduleType"
        :options="[
          { label: 'Daily', value: 'D' },
          { label: 'Weekly', value: 'W' },
          { label: 'Monthly', value: 'M' },
          { label: 'Complex', value: 'X' },
          { label: 'Cascade', value: 'C' },
        ]"
        label="Scheduler type"
        @update:model-value="scheduleTypeChanged" />

      <q-input class="col" outlined v-model="scheduleObject.mday" label="Month" v-if="scheduleType === 'X'">
        <template v-slot:append>
          <q-btn round dense flat icon="add">
            <q-menu>
              <q-list dense class="text-no-wrap">
                <q-item clickable v-close-popup v-for="menu in examples.mday" :key="menu.menuText">
                  <q-item-section @click="scheduleObject.mday = menu.exampleText">
                    {{ menu.menuText }}
                  </q-item-section>
                </q-item>
                <q-separator />
              </q-list>
            </q-menu>
          </q-btn>
        </template>
      </q-input>

      <q-input class="col" outlined v-model="scheduleObject.wday" label="Week" v-if="scheduleType === 'X'">
        <template v-slot:append>
          <q-btn round dense flat icon="add">
            <q-menu>
              <q-list dense class="text-no-wrap">
                <q-item clickable v-close-popup v-for="menu in examples.wday" :key="menu.menuText">
                  <q-item-section @click="scheduleObject.wday = menu.exampleText">
                    {{ menu.menuText }}
                  </q-item-section>
                </q-item>
                <q-separator />
              </q-list>
            </q-menu>
          </q-btn>
        </template>
      </q-input>

      <q-icon class="q-mt-lg" name="fas fa-at" size="35px" color="blue-grey-3" />

      <q-select
        v-if="scheduleType == 'W'"
        class="col"
        outlined
        emit-value
        multiple
        map-options
        v-model="scheduleObject.wday"
        :rules="[(val) => (val && val.length > 0) || 'You must select at least one day']"
        :options="[
          { label: 'Monday', value: 1 },
          { label: 'Tuesday', value: 2 },
          { label: 'Wednesday', value: 3 },
          { label: 'Thursday', value: 4 },
          { label: 'Friday', value: 5 },
          { label: 'Saturday', value: 6 },
          { label: 'Sunday', value: 7 },
        ]"
        label="Run on days of week:">
        <template v-slot:option="{ itemProps, opt, selected, toggleOption }">
          <q-item v-bind="itemProps">
            <q-item-section>
              <q-item-label v-html="opt.label" />
            </q-item-section>
            <q-item-section side>
              <q-toggle :model-value="selected" @update:model-value="toggleOption(opt)" />
            </q-item-section>
          </q-item>
        </template>
      </q-select>

      <q-select
        v-if="scheduleType == 'M'"
        class="col"
        outlined
        emit-value
        multiple
        v-model="scheduleObject.mday"
        :rules="[(val) => (val && val.length > 0) || 'You must select at least one day']"
        :options="[
          { label: '1', value: 1 },
          { label: '2', value: 2 },
          { label: '3', value: 3 },
          { label: '4', value: 4 },
          { label: '5', value: 5 },
          { label: '6', value: 6 },
          { label: '7', value: 7 },
          { label: '8', value: 8 },
          { label: '9', value: 9 },
          { label: '10', value: 10 },
          { label: '11', value: 11 },
          { label: '12', value: 12 },
          { label: '13', value: 13 },
          { label: '14', value: 14 },
          { label: '15', value: 15 },
          { label: '16', value: 16 },
          { label: '17', value: 17 },
          { label: '18', value: 18 },
          { label: '19', value: 19 },
          { label: '20', value: 20 },
          { label: '21', value: 21 },
          { label: '22', value: 22 },
          { label: '23', value: 23 },
          { label: '24', value: 24 },
          { label: '25', value: 25 },
          { label: '26', value: 26 },
          { label: '27', value: 27 },
          { label: '28', value: 28 },
          { label: '29', value: 29 },
          { label: '30', value: 30 },
          { label: '31', value: 31 },
        ]"
        label="Run on days of month:">
        <template v-slot:option="{ itemProps, opt, selected, toggleOption }">
          <q-item v-bind="itemProps">
            <q-item-section>
              <q-item-label v-html="opt.label" />
            </q-item-section>
            <q-item-section side>
              <q-toggle :model-value="selected" @update:model-value="toggleOption(opt)" />
            </q-item-section>
          </q-item>
        </template>
      </q-select>

      <q-select
        v-if="scheduleType === 'C'"
        class="col"
        use-input
        hide-selected
        fill-input
        outlined
        emit-value
        map-options
        @filter="filterControlCatalogue"
        v-model="scheduleObject.trigger_id"
        :options="triggerOptions"
        label="Control (trigger)"
        :rules="[(val) => (val && val > 0) || 'You must select a control']">
      </q-select>

      <q-input
        class="col"
        outlined
        v-model="scheduleObject.hour"
        :rules="[(val) => String(val ?? '').length > 0 || 'Must have a value']"
        label="Hour"
        v-if="scheduleType === 'X'">
        <template v-slot:append>
          <q-btn round dense flat icon="add">
            <q-menu>
              <q-list dense class="text-no-wrap">
                <q-item clickable v-close-popup v-for="menu in examples.hour" :key="menu.menuText">
                  <q-item-section @click="scheduleObject.hour = menu.exampleText">
                    {{ menu.menuText }}
                  </q-item-section>
                </q-item>
                <q-separator />
              </q-list>
            </q-menu>
          </q-btn>
        </template>
      </q-input>

      <q-input
        class="col"
        outlined
        v-model="scheduleObject.min"
        :rules="[(val) => String(val ?? '').length > 0 || 'Must have a value']"
        label="Minute"
        v-if="scheduleType === 'X'">
        <template v-slot:append>
          <q-btn round dense flat icon="add">
            <q-menu>
              <q-list dense class="text-no-wrap">
                <q-item clickable v-close-popup v-for="menu in examples.min" :key="menu.menuText">
                  <q-item-section @click="scheduleObject.min = menu.exampleText">
                    {{ menu.menuText }}
                  </q-item-section>
                </q-item>
                <q-separator />
              </q-list>
            </q-menu>
          </q-btn>
        </template>
      </q-input>

      <q-input
        class="col"
        outlined
        v-model="scheduleObject.sec"
        :rules="[(val) => String(val ?? '').length > 0 || 'Must have a value']"
        label="Second"
        v-if="scheduleType === 'X'">
        <template v-slot:append>
          <q-btn round dense flat icon="add">
            <q-menu>
              <q-list dense class="text-no-wrap">
                <q-item clickable v-close-popup v-for="menu in examples.sec" :key="menu.menuText">
                  <q-item-section @click="scheduleObject.sec = menu.exampleText">
                    {{ menu.menuText }}
                  </q-item-section>
                </q-item>
                <q-separator />
              </q-list>
            </q-menu>
          </q-btn>
        </template>
      </q-input>

      <q-input
        v-if="scheduleType !== 'X' && scheduleType !== 'C'"
        class="col"
        outlined
        v-model="scheduleTimepicker"
        mask="fulltime"
        :rules="[(val) => /^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$/.test(val) || 'Must be a valid time (HH:mm:ss) format']"
        @update:model-value="scheduleDateTimeChanged">
        <template v-slot:append>
          <q-icon name="access_time" class="cursor-pointer">
            <q-popup-proxy cover transition-show="scale" transition-hide="scale">
              <q-time v-model="scheduleTimepicker" with-seconds format24h color="teal">
                <div class="row items-center justify-end">
                  <q-btn v-close-popup label="Save" color="teal" flat @click="scheduleDateTimeChanged" />
                </div>
              </q-time>
            </q-popup-proxy>
          </q-icon>
        </template>
      </q-input>
    </div>
  </div>
</template>

<script>
import { mapActions, mapState } from "vuex";
import { notifyError } from "../api";
import { scheduleType, scheduleTime } from "../utils/schedule";

export default {
  // modelValue is the parent's schedule object and is edited in place.
  props: {
    modelValue: { type: Object, required: true },
  },
  data() {
    return {
      scheduleType: null,
      scheduleTimepicker: null,
      controlFilter: "",

      examples: {
        mday: [
          { menuText: "First day of the month", exampleText: "1" },
          { menuText: "First 3 days of the month", exampleText: "1-3" },
          { menuText: "Repeat every third day", exampleText: "/3" },
          { menuText: "Clear value (run every day of the month)", exampleText: "" },
        ],
        wday: [
          { menuText: "On Monday", exampleText: "1" },
          { menuText: "On Monday and Friday", exampleText: "1,5" },
          { menuText: "Between Monday and Friday", exampleText: "1-5" },
          { menuText: "Clear value (run every day of week)", exampleText: "" },
        ],
        hour: [
          { menuText: "At 8 o'clock in the morning", exampleText: "8" },
          { menuText: "At 8 and 15 o'clock", exampleText: "8,15" },
          { menuText: "Between 8 and 17 o'clock", exampleText: "8-17" },
          { menuText: "Run every hour", exampleText: "/1" },
          { menuText: "Every six hours", exampleText: "/6" },
        ],
        min: [
          { menuText: "On the full hour", exampleText: "0" },
          { menuText: "Every 15 minutes", exampleText: "/15" },
        ],
        sec: [
          { menuText: "On the full minute", exampleText: "0" },
          { menuText: "Every 30 seconds", exampleText: "/30" },
        ],
      },
    };
  },
  computed: {
    ...mapState(["controlCatalogue"]),
    scheduleObject() {
      return this.modelValue;
    },
    triggerOptions() {
      const needle = this.controlFilter.toLowerCase();
      return this.controlCatalogue
        .filter((control) => control.control_name.toLowerCase().includes(needle))
        .map((control) => ({ label: control.control_name, value: control.control_id }));
    },
  },
  methods: {
    ...mapActions(["updateControlCatalogue"]),
    filterControlCatalogue(val, update) {
      update(() => {
        this.controlFilter = val;
      });
    },
    async scheduleTypeChanged() {
      if (this.scheduleType === "C") {
        this.scheduleObject.mday = null;
        this.scheduleObject.wday = null;
        this.scheduleObject.hour = null;
        this.scheduleObject.min = null;
        this.scheduleObject.sec = null;
        this.scheduleObject.trigger_id = null;
      } else {
        this.scheduleObject.mday = null;
        this.scheduleObject.wday = null;
        this.scheduleObject.hour = "8";
        this.scheduleObject.min = "15";
        this.scheduleObject.sec = "0";
        this.scheduleObject.trigger_id = null;
        this.scheduleTimepicker = "08:15:00";
      }
    },
    scheduleDateTimeChanged() {
      const [hour, min, sec] = this.scheduleTimepicker.split(":");
      this.scheduleObject.hour = String(Number(hour));
      this.scheduleObject.min = String(Number(min));
      this.scheduleObject.sec = String(Number(sec));
    },
    // Derive the editor state from the schedule; runs again when the parent swaps in another schedule
    // (version switch, reload after a remote change).
    initSchedule() {
      this.scheduleType = scheduleType(this.scheduleObject);
      this.scheduleTimepicker = scheduleTime(this.scheduleObject);
    },
  },
  watch: {
    modelValue() {
      this.initSchedule();
    },
  },
  mounted() {
    this.initSchedule();
    this.updateControlCatalogue().catch((error) => notifyError("Failed to load controls.", error));
  },
};
</script>

<style></style>
