// @ts-check
import node from "@astrojs/node";
import react from "@astrojs/react";
import mdx from "@astrojs/mdx";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

export default defineConfig({
  site: process.env.PUBLIC_SITE_URL?.replace(/\/$/, "") || "https://iguanacomedy.com",
  output: "server",
  adapter: node({ mode: "standalone" }),
  integrations: [react(), mdx()],
  vite: {
    plugins: [tailwindcss()],
  },
});
