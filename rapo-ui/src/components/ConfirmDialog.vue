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
export default {
  props: ["action", "argument", "icon", "text"],
  data() {
    return {
      visible: false,
    };
  },
};
</script>
