import { createApp } from "vue";

import { Quasar } from "quasar";
import quasarUserOptions from "./quasar-user-options";

import App from "./App.vue";
import router from "./router.js";
import store from "./store";
import { initSocket } from "./socket";
import { keyboard } from "./utils/keyboard";
import { readonlyGuard } from "./utils/readonlyGuard";
import { applyTheme, readTheme } from "./utils/theme";

const app = createApp(App);

app.use(Quasar, quasarUserOptions);
app.use(router);
app.use(store);
app.directive("keyboard", keyboard);
app.directive("readonly-guard", readonlyGuard);
// $can(area, level): whether the signed-in token reaches that level, for the v-if of actions (utils/scopes.js).
app.config.globalProperties.$can = (area, level = "view") => store.getters.can(area, level);
applyTheme(readTheme());

initSocket(store);

app.mount("#app");
