import "./styles/quasar.sass";
import iconSet from "quasar/icon-set/fontawesome-v5.js";
import "@quasar/extras/roboto-font/roboto-font.css";
import "@quasar/extras/material-icons/material-icons.css";
import "@quasar/extras/fontawesome-v5/fontawesome-v5.css";

import { Dialog, LoadingBar, Notify, Cookies } from "quasar";

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
          icon: "close",
          color: "white",
          round: true,
          handler: () => {
            /* ... */
          },
        },
      ],
    },
  },
  plugins: { Dialog, LoadingBar, Notify, Cookies },
  iconSet: iconSet,
};
