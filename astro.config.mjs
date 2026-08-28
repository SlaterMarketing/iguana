// @ts-check
import cloudflare from "@astrojs/cloudflare";
import react from "@astrojs/react";
import mdx from "@astrojs/mdx";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

export default defineConfig({
  site: process.env.PUBLIC_SITE_URL?.replace(/\/$/, "") || "https://iguanacomedy.com",
  output: "server",
  adapter: cloudflare({
    platformProxy: {
      enabled: true,
    },
  }),
  integrations: [react(), mdx()],
  redirects: {
    "/es": "/es/",
    "/venues": { status: 301, destination: "/en/locations" },
    "/venues/[...path]": { status: 301, destination: "/en/locations" },
    "/private-events": { status: 301, destination: "/en/work-with-us/#private-events" },
    "/investors": { status: 301, destination: "/en/work-with-us/#investors" },
    "/comedy-for-everyone": { status: 301, destination: "/en/about" },
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
