<template>
  <span @click="visible = true">
    <slot></slot>
  </span>

  <q-dialog v-model="visible" persistent>
    <q-card>
      <q-card-section class="row items-center">
        <q-avatar :icon="icon" color="primary" text-color="white" />
        <span class="q-ml-sm">{{ text }}</span>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn label="Yes" color="primary" v-close-popup="-1" @click="action(argument)" />
        <q-btn flat label="No" color="primary" v-close-popup="-1" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { useQuasar } from "quasar";

export default {
  props: ["action", "argument", "icon", "text"],
  data() {
    return {
      visible: false,
      range: false,
      selectDate: new Date().toISOString().substring(0, 10),
      $q: useQuasar(),
    };
  },
  methods: {
    rangeChange() {
      var date = new Date();
      var toDate = new Date(date.setDate(date.getDate() - 2)).toISOString().substring(0, 10);
      var fromDate = new Date(date.setDate(date.getDate() - 1)).toISOString().substring(0, 10);
      if (this.range) {
        this.selectDate = {
          from: fromDate,
          to: toDate,
        };
      } else {
        this.selectDate = fromDate;
      }
    },
    runControl() {
      this.$q.loadingBar.start();
      var url = "";
      if (this.range) {
        url =
          "/api/run-control?name=" + this.control.control_name + "&date_from=" + this.selectDate.from + "&date_to=" + this.selectDate.to;
      } else {
        url = "/api/run-control?name=" + this.control.control_name + "&date=" + this.selectDate;
      }

      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // body: JSON.stringify({ date: this.selectDate }),
      })
        .then((response) => {
          if (response.ok) {
            this.$q.notify({ type: "positive", message: "Control " + this.control.control_name + " queued for execution" });
            return response.json();
          } else {
            this.$q.notify({ type: "negative", message: "Control " + this.control.control_name + " failed" });
          }
        })
        .then(() => {
          //this.datasourceList = data;
          this.$q.loadingBar.stop();
        });
    },
  },
};
</script>
