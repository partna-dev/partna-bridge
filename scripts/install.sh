#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

say() { printf '%s\n' "$*"; }
fail() { printf 'ошибка: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "нужен docker"
docker compose version >/dev/null 2>&1 || fail "нужен docker compose v2"

if [ ! -f .env ]; then
  cp .env.example .env
  say "создан .env из шаблона"
fi

set_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" .env && rm -f .env.bak
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

value_of() { grep -E "^$1=" .env | head -1 | cut -d= -f2-; }

if [ -z "$(value_of BRIDGE_BRIDGE_TOKEN)" ]; then
  set_env BRIDGE_BRIDGE_TOKEN "$(openssl rand -hex 24)"
  say "выпущен BRIDGE_BRIDGE_TOKEN"
fi
if [ -z "$(value_of BRIDGE_WEBHOOK_SECRET)" ]; then
  set_env BRIDGE_WEBHOOK_SECRET "$(openssl rand -hex 24)"
  say "выпущен BRIDGE_WEBHOOK_SECRET"
fi

missing=0
for key in BRIDGE_ENGINE_API_KEY BRIDGE_DESTINATION_URL; do
  if [ -z "$(value_of "$key")" ]; then
    say "не заполнено: $key"
    missing=1
  fi
done
[ "$missing" -eq 0 ] || fail "заполните переменные в .env и запустите снова"

public_url="$(value_of BRIDGE_PUBLIC_URL)"
case "$public_url" in
  https://*) ;;
  *) say "внимание: BRIDGE_PUBLIC_URL не https, cookie не получит флаг Secure" ;;
esac

say "собираю и поднимаю контейнер"
docker compose up -d --build

port="$(value_of BRIDGE_PUBLIC_URL | sed -E 's|.*:([0-9]+).*|\1|')"
health_url="http://127.0.0.1:${port:-8020}/health"

for _ in $(seq 1 30); do
  if curl -fsS "$health_url" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! body="$(curl -fsS "$health_url" 2>/dev/null)"; then
  fail "мост не отвечает на $health_url, смотрите: docker compose logs bridge"
fi

say ""
say "мост поднят: $body"
say ""
say "осталось:"
say "1. зарегистрировать вебхук в ядре:"
say "   partner-network webhook-set --tenant <тенант> \\"
say "     --url ${public_url%/}/webhooks/engine \\"
say "     --secret $(value_of BRIDGE_WEBHOOK_SECRET)"
say "2. проверить код партнёра: ${public_url%/}/r/<код>"
say "3. вписать в сайт ${public_url%/} как адрес моста"
