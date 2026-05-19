const key = process.env.PUBLIC_KINTANA_API_KEY?.trim();
const baseUrl = process.env.PUBLIC_KINTANA_BASE_URL?.trim();

if (!key || !baseUrl) {
  console.error("\n[Kintana build] Missing required variables at image build time.\n");
  if (!key) console.error("  - PUBLIC_KINTANA_API_KEY is empty");
  if (!baseUrl) console.error("  - PUBLIC_KINTANA_BASE_URL is empty");
  console.error(
    "\nDokploy: open your app → Environment → add both values → enable “Available at Buildtime” (or Build Args) → redeploy.\n" +
      "Runtime-only env vars do not update a static Astro site; the image must rebuild with these set.\n",
  );
  process.exit(1);
}

console.log("[Kintana build] API key and base URL present.");
