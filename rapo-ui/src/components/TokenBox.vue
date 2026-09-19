<template>
  <div class="absolute-center" v-if="!tokenValidationInProgress">
    <q-card class="my-card">
      <q-card-section class="column">
        <div class="text-overline">Please enter a valid token to connect to backend API</div>
        <q-input v-model="token" outlined :type="isPwd ? 'password' : 'text'" hint="RAPO token" @keyup.enter="connect(token)" autofocus>
          <template v-slot:append>
            <q-icon :name="isPwd ? 'visibility_off' : 'visibility'" class="cursor-pointer" @click="isPwd = !isPwd" />
          </template>
        </q-input>
        <q-toggle color="teal" v-model="rememberToken" label="Remember token" />
        <q-btn color="teal" label="Connect" @click="connect(token)" />
        <p class="text-red q-mt-md" v-if="connectError">Error connecting. Check token and try again!</p>
      </q-card-section>
    </q-card>
  </div>
  <div class="absolute-center" v-if="tokenValidationInProgress">
    <q-spinner-audio color="teal" size="10em" />
  </div>
</template>

<script>
import { mapActions, mapGetters } from "vuex";
import { useQuasar } from "quasar";

export default {
  data() {
    return {
      token: "",
      isPwd: true,
      rememberToken: false,
      connectError: false,
      tokenValidationInProgress: false,
      redirectPath: this.$route.query.redirect || "/controls",
      $q: useQuasar(),
    };
  },
  methods: {
    ...mapActions(["validateToken", "updateEnvVersion", "updateEnvInfo", "updateEnvParameters"]),
    async connect(token) {
      this.tokenValidationInProgress = true;
      const validated = await this.validateToken(token);

      if (!validated) {
        this.connectError = true;
        this.$q.cookies.remove("rapo_token");
      } else {
        this.updateEnvVersion();
        this.updateEnvInfo();
        this.updateEnvParameters();
        if (this.rememberToken) {
          this.$q.cookies.set("rapo_token", token, { SameSite: "Strict", expires: "365d" });
        }
        this.$router.push(this.redirectPath);
      }

      this.tokenValidationInProgress = false;
    },
  },
  computed: {
    ...mapGetters(["getTokenIsValid"]),
  },
  mounted() {
    if (this.$q.cookies.has("rapo_token")) {
      const token = this.$q.cookies.get("rapo_token");
      this.connect(token);
    }
  },
};
</script>
