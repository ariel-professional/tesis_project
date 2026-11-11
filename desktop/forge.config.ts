import type { ForgeConfig } from "@electron-forge/shared-types";
import { MakerSquirrel } from "@electron-forge/maker-squirrel";
import { WebpackPlugin } from "@electron-forge/plugin-webpack";

const config: ForgeConfig = {
  packagerConfig: {
    asar: true,
    extraResource: ["resources/python", "../examples"],
  },
  rebuildConfig: {},
  makers: [new MakerSquirrel({})],
  plugins: [
    new WebpackPlugin({
      // Forge's default response header blocks blob images even when the HTML
      // policy allows them. Keep both policies identical in development.
      devContentSecurityPolicy: require("./scripts/renderer-csp.cjs"),
      mainConfig: "./webpack.main.cjs",
      renderer: {
        config: "./webpack.renderer.cjs",
        entryPoints: [
          {
            html: "./src/renderer/index.html",
            js: "./src/renderer/index.tsx",
            name: "main_window",
            preload: { js: "./src/preload/index.ts" },
          },
        ],
      },
    }),
  ],
};

export default config;
