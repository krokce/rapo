import { createApp } from "vue";

import { Quasar } from "quasar";
import quasarUserOptions from "./quasar-user-options";

import App from "./App.vue";
import router from "./router.js";
import store from "./store";
import { initSocket } from "./socket";

const app = createApp(App);

app.use(Quasar, quasarUserOptions);
app.use(router);
app.use(store);

initSocket(store);

app.mount("#app");
