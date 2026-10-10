const path = require("path");
const { defineConfig } = require("@vue/cli-service");
module.exports = defineConfig({
  transpileDependencies: ["quasar"],

  // Build straight into the Python package that FastAPI serves the UI from.
  outputDir: path.resolve(__dirname, "../rapo/web/ui"),

  // ECharts is its own chunk, loaded with the first page that charts (the Dashboard, the analysis pages) and cached
  // once for all of them.
  chainWebpack: (config) => {
    config.optimization.splitChunks({
      ...config.optimization.get("splitChunks"),
      cacheGroups: {
        ...(config.optimization.get("splitChunks") || {}).cacheGroups,
        echarts: {
          name: "echarts",
          test: /[\\/]node_modules[\\/](echarts|zrender|vue-echarts)[\\/]/,
          chunks: "async",
          priority: 20,
          enforce: true,
        },
      },
    });
  },

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
