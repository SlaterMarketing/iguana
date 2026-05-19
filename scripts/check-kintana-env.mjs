const key = process.env.PUBLIC_KINTANA_API_KEY?.trim();
const baseUrl = process.env.PUBLIC_KINTANA_BASE_URL?.trim();

if (!key || !baseUrl) {
  console.error("\n[Kintana build] Missing required variables at image build time.\n");
  if (!key) console.error("  - PUBLIC_KINTANA_API_KEY is empty");
  if (!baseUrl) console.error("  - PUBLIC_KINTANA_BASE_URL is empty");
  console.error(
    "\nAdd PUBLIC_KINTANA_API_KEY and PUBLIC_KINTANA_BASE_URL in Dokploy → Environment, then restart the app.\n",
  );
  process.exit(1);
}

console.log("[Kintana build] API key and base URL present.");
