import fs from "node:fs";
import path from "node:path";

const cwd = process.cwd();
const srcRoot = path.join(cwd, "src");

function walk(dir, fn) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p, fn);
    else if (/\.(astro|mdx)$/.test(name)) fn(p);
  }
}

function fixFile(filePath) {
  const dir = path.dirname(filePath);
  const relToSrc = path.relative(dir, srcRoot);
  const posixRel = relToSrc.split(path.sep).join("/");
  const prefix = posixRel === "" ? "." : posixRel;

  let s = fs.readFileSync(filePath, "utf8");
  const orig = s;

  s = s.replace(/from "((?:\.\.\/)+)([^"]+)"/g, (full, _dots, suffix) => {
    if (
      suffix.startsWith("layouts/") ||
      suffix.startsWith("components/") ||
      suffix.startsWith("content/") ||
      suffix.startsWith("lib/") ||
      suffix.startsWith("i18n/")
    ) {
      return `from "${prefix}/${suffix}"`;
    }
    return full;
  });

  s = s.replace(/layout:\s*((?:\.\.\/)+)\s*(\S+)/g, (full, _dots, rest) => {
    if (rest.startsWith("layouts/")) return `layout: ${prefix}/${rest}`;
    return full;
  });

  if (s !== orig) {
    fs.writeFileSync(filePath, s);
    console.log("fixed", path.relative(cwd, filePath));
  }
}

walk(path.join(cwd, "src/pages/en"), fixFile);
