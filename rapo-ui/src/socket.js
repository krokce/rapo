import { io } from "socket.io-client";

// Live updates pushed by the backend when control runs ("runs:changed") or
// control configurations ("controls:changed") change in the database.
// Payloads: { resync, process_ids, control_names } and { resync, control_ids };
// resync means rows were deleted and any view may be affected.
const socket = io({
  path: "/api/socket.io",
  autoConnect: false,
  auth: (cb) => cb({ token: socket.store ? socket.store.getters.getToken : "" }),
});

export function initSocket(store) {
  socket.store = store;
  socket.on("connect", () => store.commit("updateSocketConnected", true));
  socket.on("disconnect", () => store.commit("updateSocketConnected", false));
  socket.on("connect_error", (err) => {
    store.commit("updateSocketConnected", false);
    console.error("Live updates connection failed:", err.message);
  });
  store.watch(
    (state) => state.tokenValue,
    (token) => {
      socket.disconnect();
      if (token) {
        socket.connect();
      }
    },
    { immediate: true }
  );
}

// Call fetchFn whenever event arrives and filter(payload) accepts it.
// Refetches are throttled to one per interval (first immediately, the rest
// merged into one trailing call), postponed while the tab is hidden, and
// forced after a reconnect since events may have been missed meanwhile.
// Returns a function that stops listening.
export function liveRefetch(event, fetchFn, { filter = null, interval = 5000 } = {}) {
  let lastRun = 0;
  let timer = null;
  let pending = false;
  let missed = false;

  const run = async () => {
    timer = null;
    if (document.hidden) {
      pending = true;
      return;
    }
    pending = false;
    lastRun = Date.now();
    try {
      await fetchFn();
    } catch (err) {
      console.error("Live refetch failed:", err);
    }
  };
  const request = () => {
    if (timer) {
      return;
    }
    const wait = lastRun + interval - Date.now();
    if (wait <= 0) {
      run();
    } else {
      timer = setTimeout(run, wait);
    }
  };
  const onEvent = (payload) => {
    if (!filter || !payload || payload.resync || filter(payload)) {
      request();
    }
  };
  const onDisconnect = () => {
    missed = true;
  };
  const onConnect = () => {
    if (missed) {
      missed = false;
      request();
    }
  };
  const onVisibility = () => {
    if (!document.hidden && pending) {
      request();
    }
  };

  socket.on(event, onEvent);
  socket.on("disconnect", onDisconnect);
  socket.on("connect", onConnect);
  document.addEventListener("visibilitychange", onVisibility);

  return () => {
    socket.off(event, onEvent);
    socket.off("disconnect", onDisconnect);
    socket.off("connect", onConnect);
    document.removeEventListener("visibilitychange", onVisibility);
    clearTimeout(timer);
  };
}

export default socket;
