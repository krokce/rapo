const path = require("path");
const { defineConfig } = require("@vue/cli-service");
module.exports = defineConfig({
  transpileDependencies: ["quasar"],

  // Build straight into the Python package that Flask serves the UI from.
  outputDir: path.resolve(__dirname, "../rapo/web/ui"),

  pluginOptions: {
    quasar: {
      importStrategy: "kebab",
      rtlSupport: false,
    },
  },
  devServer: {
    proxy: {
      '/api': {
        target: process.env.RAPO_API_URL || 'http://localhost:7005',
        changeOrigin: true,
        ws: true
      }
    }
  }
});
