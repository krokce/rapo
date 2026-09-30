import "./styles/quasar.sass";
import "./styles/app.sass";
import iconSet from "quasar/icon-set/fontawesome-v5.js";
import "@quasar/extras/roboto-font/roboto-font.css";
import "@quasar/extras/fontawesome-v5/fontawesome-v5.css";
import "@fontsource/roboto-mono/latin-400.css";
import "@fontsource/roboto-mono/latin-700.css";
import "@fontsource/roboto-mono/latin-ext-400.css";
import "@fontsource/roboto-mono/latin-ext-700.css";

import { Dark, Dialog, LoadingBar, Notify, Cookies } from "quasar";

// To be used on app.use(Quasar, { ... })
export default {
  config: {
    loadingBar: { color: "teal", size: "2px", position: "top" },
    notify: {
      position: "bottom-right",
      progress: true,
      color: "teal",
      icon: "fas fa-info-circle",
      actions: [
        {
          icon: "fas fa-times",
          color: "white",
          round: true,
          handler: () => {
            /* ... */
          },
        },
      ],
    },
  },
  plugins: { Dark, Dialog, LoadingBar, Notify, Cookies },
  iconSet: iconSet,
};
