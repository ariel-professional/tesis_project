const path = require("node:path");
const PdfAssetsPlugin = require("./scripts/pdf-assets.cjs");

/** @type {import("webpack").Configuration} */
module.exports = {
  plugins: [new PdfAssetsPlugin()],
  // The renderer CSP intentionally disallows eval(). Webpack's development
  // default uses eval-based source maps, which prevents the whole React bundle
  // from executing and leaves Electron with an empty page.
  devtool: "source-map",
  module: {
    rules: [
      { test: /\.tsx?$/, use: "ts-loader", exclude: /node_modules/ },
      { test: /\.css$/, use: ["style-loader", "css-loader"] },
    ],
  },
  resolve: {
    extensions: [".ts", ".tsx", ".js"],
    modules: [path.resolve(__dirname, "node_modules"), "node_modules"],
    alias: {
      "@domain-ui-sdk": path.resolve(__dirname, "domain-ui-sdk/src/index.ts"),
      "@domain-ui-kit": path.resolve(__dirname, "domain-ui-kit/src/index.ts"),
    },
  },
};
