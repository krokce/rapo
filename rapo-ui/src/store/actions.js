import { LoadingBar } from "quasar";

export default {
  async updateControlCatalogue(context) {
    LoadingBar.start();
    try {
      const response = await fetch("/api/get-all-controls", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${context.getters.getToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      context.commit("updateControlCatalogue", data);

      return data;
    } catch (err) {
      console.error("Failed to load controls:", err);
      throw err; // re-throw so component can catch if needed
    } finally {
      LoadingBar.stop();
    }
  },
  async updateControlResults(context) {
    LoadingBar.start();
    try {
      const response = await fetch("/api/get-control-runs", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${context.getters.getToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      context.commit("updateControlResults", data);
      return data;
    } catch (err) {
      console.error("Failed to load control runs:", err);
      throw err; // re-throw so component can catch if needed
    } finally {
      LoadingBar.stop();
    }
  },
  async updateEnvVersion(context) {
    try {
      const response = await fetch("/api/version", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${context.getters.getToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      context.commit("updateEnvVersion", data);

      return data;
    } catch (err) {
      console.error("Failed to load version:", err);
      throw err; // re-throw so component can catch if needed
    } finally {
      LoadingBar.stop();
    }
  },  
  async updateEnvInfo(context) {
    try {
      const response = await fetch("/api/info", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${context.getters.getToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      context.commit("updateEnvInfo", data);

      return data;
    } catch (err) {
      console.error("Failed to load info:", err);
      throw err; // re-throw so component can catch if needed
    } finally {
      LoadingBar.stop();
    }
  },  
  async updateEnvParameters(context) {
    try {
      const response = await fetch("/api/parameters", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${context.getters.getToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      context.commit("updateEnvParameters", data);

      return data;
    } catch (err) {
      console.error("Failed to load parameters:", err);
      throw err; // re-throw so component can catch if needed
    } finally {
      LoadingBar.stop();
    }
  },  
  updateHideSearch(context, payload) {
    context.commit("updateHideSearch", payload);
  },
  updateSearch(context, payload) {
    context.commit("updateSearch", payload);
  },
  removeToken(context) {
    context.commit("updateTokenValue", "");
  },
  async validateToken(context, token) {
    const response = await fetch("/api/help", {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
      context.commit("updateTokenValue", token);
      return true;
    } else {
      context.commit("updateTokenValue", "");
      return false;
    }
  },
};
