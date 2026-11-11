/** @type {import("webpack").Configuration} */
module.exports = {
  entry: "./src/main/index.ts",
  module: {
    rules: [{ test: /\.tsx?$/, use: "ts-loader", exclude: /node_modules/ }],
  },
  resolve: { extensions: [".ts", ".tsx", ".js"] },
};
