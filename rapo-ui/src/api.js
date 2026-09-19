import { Cookies, LoadingBar, Notify } from "quasar";
import store from "./store";
import router from "./router";

// Forget the token and go to the token page, coming back to the current page after reconnecting.
export function signOut() {
  Cookies.remove("rapo_token");
  store.commit("updateTokenValue", "");
  const current = router.currentRoute.value;
  if (current.name !== "token") {
    router.push({ name: "token", query: { redirect: current.fullPath } });
  }
}

// Single entry point for /api calls: adds the Bearer token, encodes query params (null values are left out),
// shows the loading bar for the duration of the request, and throws an Error with FastAPI's `detail` on HTTP
// errors. A rejected token (401) signs the user out.
export async function api(path, { method = "GET", params, body, loadingBar = true } = {}) {
  const query = params ? "?" + new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)) : "";
  const headers = { Authorization: `Bearer ${store.getters.getToken}` };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  if (loadingBar) {
    LoadingBar.start();
  }
  try {
    const response = await fetch("/api/" + path + query, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    if (response.status === 401) {
      signOut();
      throw new Error("Token rejected, please reconnect.");
    }
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : `${response.status} ${response.statusText}`);
    }
    return await response.json();
  } finally {
    if (loadingBar) {
      LoadingBar.stop();
    }
  }
}

export function notifyError(message, error) {
  Notify.create({ type: "negative", message: `${message} ${error.message}` });
}
