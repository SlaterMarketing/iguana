// @ts-check
import cloudflare from "@astrojs/cloudflare";
import node from "@astrojs/node";
import react from "@astrojs/react";
import mdx from "@astrojs/mdx";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

// Cloudflare Pages by default; ASTRO_ADAPTER=node builds a standalone Node server (VPS / Docker).
const useNode = process.env.ASTRO_ADAPTER === "node";
const edgeReactAliases =
  import.meta.env.PROD && !useNode
    ? {
        "react-dom/server": "react-dom/server.edge",
        "react-dom/server.browser": "react-dom/server.edge",
      }
    : undefined;

export default defineConfig({
  // Normally `dist`. The deploy sets it to build BESIDE the running server and rename afterwards, because the
  // Node adapter resolves route modules lazily and a rebuild in place 500s every route not yet imported.
  ...(process.env.ASTRO_OUT_DIR ? { outDir: process.env.ASTRO_OUT_DIR } : {}),
  site: process.env.PUBLIC_SITE_URL?.replace(/\/$/, "") || "https://iguanacomedy.com",
  output: "server",
  session: {
    driver: "memory",
  },
  adapter: useNode
    ? node({ mode: "standalone" })
    : cloudflare({
        platformProxy: {
          enabled: true,
        },
        imageService: "compile",
      }),
  integrations: [react(), mdx()],
  redirects: {
    "/venues": { status: 301, destination: "/en/locations" },
    "/venues/[...path]": { status: 301, destination: "/en/locations" },
    "/private-events": { status: 301, destination: "/en/work-with-us/#private-events" },
    "/investors": { status: 301, destination: "/en/work-with-us/#investors" },
    "/comedy-for-everyone": { status: 301, destination: "/en/about" },
  },
  vite: {
    plugins: [tailwindcss()],
    resolve: {
      alias: edgeReactAliases,
    },
    ssr: {
      resolve: {
        alias: edgeReactAliases,
      },
    },
  },
});
