#!/bin/bash
set -euo pipefail

SITE="proxycraft.tech"
PROJECT="proxycraft-landing"
INDEXNOW_KEY="509ba55d653644589424addd0fd8322a"
SITEMAP_URL="https://${SITE}/sitemap-index.xml"

echo "🔨 Building ${SITE}..."
rm -rf dist
npm run build

echo "🚀 Deploying to Cloudflare Pages..."
npx wrangler pages deploy dist --project-name="${PROJECT}" --branch=main --commit-dirty=true

echo "📡 Notifying IndexNow (Bing + Yandex)..."
URLS=$(curl -s "${SITEMAP_URL}" | grep -o '<loc>[^<]*</loc>' | sed 's/<\/*loc>//g')
SITEMAP_URLS=""
for sitemap in $URLS; do
  PAGE_URLS=$(curl -s "$sitemap" | grep -o '<loc>[^<]*</loc>' | sed 's/<\/*loc>//g')
  SITEMAP_URLS="${SITEMAP_URLS}${PAGE_URLS}"$'\n'
done

URL_JSON=$(echo "$SITEMAP_URLS" | grep -v '^$' | head -100 | jq -R . | jq -s .)

curl -s -X POST "https://api.indexnow.org/indexnow" \
  -H "Content-Type: application/json" \
  -d "{
    \"host\": \"${SITE}\",
    \"key\": \"${INDEXNOW_KEY}\",
    \"keyLocation\": \"https://${SITE}/${INDEXNOW_KEY}.txt\",
    \"urlList\": ${URL_JSON}
  }" -w "\nIndexNow: HTTP %{http_code}\n"

echo "📡 Pinging Yandex..."
curl -s -o /dev/null -w "Yandex Sitemap Ping: HTTP %{http_code}\n" \
  "https://webmaster.yandex.ru/ping?sitemap=${SITEMAP_URL}"

echo "✅ Done! ${SITE} deployed and search engines notified."
