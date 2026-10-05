/** Remove macOS AppleDouble sidecars that confuse Jest, ESLint, and CRA on T7. */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const scanRoots = ["src", "public", "build", "node_modules"];
const appleDoubleMagic = Buffer.from([0x00, 0x05, 0x16, 0x07]);
let removed = 0;

/** Check the file signature before removing a `._` file. */
function isAppleDouble(filePath) {
  const handle = fs.openSync(filePath, "r");
  try {
    const signature = Buffer.alloc(4);
    return fs.readSync(handle, signature, 0, 4, 0) === 4 && signature.equals(appleDoubleMagic);
  } finally {
    fs.closeSync(handle);
  }
}

/** Walk first-party files and dependencies without following symlinked folders. */
function cleanDirectory(directory) {
  if (!fs.existsSync(directory)) return;
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      cleanDirectory(entryPath);
    } else if (entry.isFile() && entry.name.startsWith("._") && isAppleDouble(entryPath)) {
      fs.unlinkSync(entryPath);
      removed += 1;
    }
  }
}

for (const root of scanRoots) cleanDirectory(path.join(projectRoot, root));
if (removed) console.log(`Removed ${removed} macOS AppleDouble sidecar files.`);
