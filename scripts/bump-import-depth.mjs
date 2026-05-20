import fs from "node:fs";
import path from "node:path";

function walk(dir, fn) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p, fn);
    else if (/\.(astro|mdx)$/.test(name)) fn(p);
  }
}

const root = path.join(process.cwd(), "src/pages/en");
walk(root, (file) => {
  let s = fs.readFileSync(file, "utf8");
  const orig = s;
  s = s.replace(
    /from "((?:\.\.\/)+)([^"]+)"/g,
    (_, dots, rest) => `from "../${dots}${rest}"`,
  );
  s = s.replace(
    /layout:\s*((?:\.\.\/)+)\s*(\S+)/g,
    (_, dots, rest) => `layout: ../${dots}${rest}`,
  );
  if (s !== orig) {
    fs.writeFileSync(file, s);
    console.log("updated", path.relative(process.cwd(), file));
  }
});
