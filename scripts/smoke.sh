#!/usr/bin/env bash
# Проверка уровня интеграции против живого моста.
#
# ./scripts/smoke.sh --level 1 --url https://bridge.example
# ./scripts/smoke.sh --level 2 --url https://bridge.example --token tkn --code IRON --user test-42
# ./scripts/smoke.sh --level 3 --url https://bridge.example --token tkn --user test-42 [--sponsor test-41]
set -uo pipefail

LEVEL=1
URL=""
TOKEN=""
CODE=""
USER_ID="test-1"
SPONSOR=""
BODY_FILE="$(mktemp)"
HEADER_FILE="$(mktemp)"
PASSED=0
FAILED=0

while [ $# -gt 0 ]; do
  case "$1" in
    --level) LEVEL="${2:-1}"; shift 2 ;;
    --url) URL="${2:-}"; shift 2 ;;
    --token) TOKEN="${2:-}"; shift 2 ;;
    --code) CODE="${2:-}"; shift 2 ;;
    --user) USER_ID="${2:-test-1}"; shift 2 ;;
    --sponsor) SPONSOR="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$URL" ]; then
  echo "нужен --url" >&2
  exit 2
fi
URL="${URL%/}"

cleanup() { rm -f "$BODY_FILE" "$HEADER_FILE"; }
trap cleanup EXIT

pass() { PASSED=$((PASSED + 1)); echo "  ok    $1"; }
fail() { FAILED=$((FAILED + 1)); echo "  FAIL  $1"; echo "        $2"; }
note() { echo; echo "$1"; }

http() {
  local method="$1" path="$2" data="${3:-}" code
  local args=(-sS -m 20 -o "$BODY_FILE" -w "%{http_code}" -X "$method" "$URL$path")
  if [ -n "$TOKEN" ]; then
    args+=(-H "Authorization: Bearer $TOKEN")
  fi
  if [ -n "$data" ]; then
    args+=(-H "Content-Type: application/json" -d "$data")
  fi
  code="$(curl "${args[@]}" 2>/dev/null)" || code="000"
  HTTP_CODE="$code"
  BODY="$(cat "$BODY_FILE" 2>/dev/null)"
}

expect_status() {
  local name="$1" expected="$2"
  case " $expected " in
    *" $HTTP_CODE "*) pass "$name ($HTTP_CODE)" ;;
    *) fail "$name" "ожидался $expected, получен $HTTP_CODE: ${BODY:0:200}" ;;
  esac
}

expect_body() {
  local name="$1" needle="$2"
  case "$BODY" in
    *"$needle"*) pass "$name" ;;
    *) fail "$name" "в ответе нет $needle: ${BODY:0:200}" ;;
  esac
}

now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

note "уровень $LEVEL, мост $URL"

note "1. Мост отвечает"
http GET /health
expect_status "GET /health" "200"
expect_body "ключ тенанта настроен" '"key_configured":true'

http GET /v1/config
expect_status "GET /v1/config" "200"
expect_body "валюта в ответе" '"currency"'

note "2. Ссылка ставит cookie"
redirect_headers="$(curl -sS -m 20 -D "$HEADER_FILE" -o /dev/null "$URL/r/TEST1" 2>/dev/null)"
redirect_code="$(awk 'tolower($1) ~ /^http\// {code=$2} END {print code}' "$HEADER_FILE")"
if [ "$redirect_code" = "302" ] || [ "$redirect_code" = "307" ]; then
  pass "GET /r/TEST1 ($redirect_code)"
else
  fail "GET /r/TEST1" "ожидался редирект, получен ${redirect_code:-нет ответа}"
fi
if grep -qi "set-cookie:.*pn_ref=TEST1" "$HEADER_FILE"; then
  pass "cookie pn_ref=TEST1"
else
  fail "cookie pn_ref=TEST1" "в заголовках нет Set-Cookie с pn_ref"
fi
if grep -qi "location:.*ref=TEST1" "$HEADER_FILE"; then
  pass "возврат с ?ref=TEST1"
else
  fail "возврат с ?ref=TEST1" "в Location нет ref=TEST1"
fi

if [ "$LEVEL" -ge 2 ]; then
  note "3. Серверный claim и ссылка партнёра"
  if [ -z "$TOKEN" ]; then
    fail "нужен --token" "уровень 2 вызывает claim с Bearer-токеном"
  elif [ -z "$CODE" ]; then
    fail "нужен --code" "без кода партнёра claim не пройдёт"
  else
    http POST /v1/claim "{\"code\":\"$CODE\",\"externalAccountId\":\"$USER_ID\"}"
    expect_status "POST /v1/claim" "200 202"
    case "$HTTP_CODE" in
      200) expect_body "привязка создана" '"memberId"' ;;
      202) expect_body "привязка в очереди" '"pending"' ;;
    esac

    http POST /v1/partner-link "{\"externalAccountId\":\"$USER_ID\"}"
    expect_status "POST /v1/partner-link" "200"
    expect_body "в ответе есть код" '"code"'
    echo "        ссылка для партнёра: $URL/r/<code>"
  fi
fi

if [ "$LEVEL" -ge 3 ]; then
  note "4. Участник из своего графа"
  if [ -z "$TOKEN" ]; then
    fail "нужен --token" "POST /v1/member требует Bearer-токен"
  else
    if [ -n "$SPONSOR" ]; then
      member_body="{\"eventId\":\"member:$USER_ID:$SPONSOR\",\"occurredAt\":\"$(now)\",\"memberId\":\"$USER_ID\",\"sponsorId\":\"$SPONSOR\",\"placementId\":\"$SPONSOR\"}"
    else
      member_body="{\"eventId\":\"member:$USER_ID:root\",\"occurredAt\":\"$(now)\",\"memberId\":\"$USER_ID\"}"
    fi
    http POST /v1/member "$member_body"
    expect_status "POST /v1/member" "200 202"
    if [ "$HTTP_CODE" = "409" ]; then
      echo "        409 значит, что участник уже связан иначе — это не сбой"
    fi
  fi
fi

echo
if [ "$FAILED" -eq 0 ]; then
  echo "итог: уровень $LEVEL пройден ($PASSED проверок)"
  exit 0
fi
echo "итог: $PASSED прошло, $FAILED не прошло"
exit 1
