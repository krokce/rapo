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
// errors (its `status` is the HTTP code). An array param is repeated (?id=1&id=2). A rejected token (401) signs the user out. With raw the Response is returned as is (e.g. for a download).
export async function api(path, { method = "GET", params, body, loadingBar = true, raw = false } = {}) {
  const entries = Object.entries(params || {})
    .filter(([, value]) => value != null)
    .flatMap(([key, value]) => (Array.isArray(value) ? value.map((item) => [key, item]) : [[key, value]]));
  const query = params ? "?" + new URLSearchParams(entries) : "";
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
      const error = new Error(typeof data.detail === "string" ? data.detail : `${response.status} ${response.statusText}`);
      error.status = response.status;
      throw error;
    }
    return raw ? response : await response.json();
  } finally {
    if (loadingBar) {
      LoadingBar.stop();
    }
  }
}

export function notifyError(message, error) {
  Notify.create({ type: "negative", message: `${message} ${error.message}` });
}
