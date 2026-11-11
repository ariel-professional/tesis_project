const fs = require("node:fs");
const path = require("node:path");

// Keep PDF.js font maps and decoders local in development and packaged builds.
class PdfAssetsPlugin {
  apply(compiler) {
    compiler.hooks.thisCompilation.tap("PdfAssetsPlugin", (compilation) => {
      compilation.hooks.processAssets.tap({
        name: "PdfAssetsPlugin",
        stage: compiler.webpack.Compilation.PROCESS_ASSETS_STAGE_ADDITIONAL,
      }, () => {
        const root = path.dirname(require.resolve("pdfjs-dist/package.json"));
        for (const directory of ["cmaps", "standard_fonts", "wasm", "iccs"]) {
          for (const name of fs.readdirSync(path.join(root, directory))) {
            const file = path.join(root, directory, name);
            if (fs.statSync(file).isFile()) compilation.emitAsset(
              `pdfjs/${directory}/${name}`,
              new compiler.webpack.sources.RawSource(fs.readFileSync(file)),
            );
          }
        }
      });
    });
  }
}
module.exports = PdfAssetsPlugin;
