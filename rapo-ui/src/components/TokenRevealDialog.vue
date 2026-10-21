<template>
  <!-- The token is forgotten only once the dialog is hidden: removing its card while it closes left the backdrop. -->
  <q-dialog v-model="shown" persistent @hide="result = null">
    <q-card v-if="result" style="width: 720px; max-width: 95vw">
      <q-card-section>
        <div class="text-h6">Token of {{ result.user_name }}</div>
        <div class="text-caption text-grey-7">
          {{ result.user_email }}{{ result.label ? ` · ${result.label}` : "" }} · expires {{ result.expires_at ? toDateTimeString(result.expires_at) : "never" }}
        </div>
      </q-card-section>
      <q-card-section class="q-pt-none">
        <q-banner dense rounded class="bg-orange-1 text-orange-10 q-mb-md">
          <template #avatar><q-icon name="fas fa-eye-slash" size="16px" /></template>
          Copy the token now: it is shown only this once. Rapo keeps only a fingerprint of it; a lost token is regenerated.
        </q-banner>
        <q-input outlined readonly :model-value="result.token" input-class="text-mono">
          <template #append>
            <q-btn flat dense icon="fas fa-copy" aria-label="Copy token" @click="copy(result.token, 'Token')">
              <q-tooltip>Copy the token</q-tooltip>
            </q-btn>
          </template>
        </q-input>
        <div class="text-caption text-grey-7 q-mt-md q-mb-xs">Sign in to the UI with it, or call the API, e.g.:</div>
        <div class="row no-wrap items-start">
          <pre class="col text-mono curl-example q-ma-none">{{ curl }}</pre>
          <q-btn flat dense icon="fas fa-copy" aria-label="Copy example" @click="copy(curl, 'Example')">
            <q-tooltip>Copy the example</q-tooltip>
          </q-btn>
        </div>
      </q-card-section>
      <q-card-actions align="right">
        <!-- The instructions only: the token is handed over by the administrator, never by mail. -->
        <q-btn flat no-caps icon="fas fa-envelope" label="Email instructions" :href="mailto" target="_blank">
          <q-tooltip>Opens a mail to the user with the address of Rapo, without the token</q-tooltip>
        </q-btn>
        <q-space />
        <q-btn color="primary" label="Done" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { copyText, toDateTimeString } from "../utils/format";

export default {
  name: "TokenRevealDialog",
  data() {
    return { shown: false, result: null };
  },
  methods: {
    toDateTimeString,
    open(result) {
      this.result = result;
      this.shown = true;
    },
    async copy(text, what) {
      try {
        await copyText(text);
        this.$q.notify({ type: "positive", message: `${what} copied to the clipboard.` });
      } catch (error) {
        this.$q.notify({ type: "negative", message: `${what} was not copied: ${error.message}` });
      }
    },
  },
  computed: {
    curl() {
      return `curl -H "Authorization: Bearer ${this.result.token}" ${window.location.origin}/api/whoami`;
    },
    mailto() {
      const r = this.result;
      const body =
        `Hello ${r.user_name},\n\nyou have an API token for Rapo (${window.location.origin})` +
        `${r.label ? ` for ${r.label}` : ""}, valid ${r.expires_at ? `until ${toDateTimeString(r.expires_at)}` : "without end"}.\n` +
        `I will hand you the token separately. Sign in at ${window.location.origin}/token, or send it as "Authorization: Bearer <token>" to the API.\n`;
      return `mailto:${encodeURIComponent(r.user_email)}?subject=${encodeURIComponent("Your Rapo API token")}&body=${encodeURIComponent(body)}`;
    },
  },
};
</script>

<style scoped>
.curl-example {
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  background: var(--rapo-header);
  padding: 8px;
  border-radius: 4px;
}
</style>
