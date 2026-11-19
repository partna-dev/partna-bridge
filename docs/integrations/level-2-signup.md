# Уровень 2 — своя регистрация клиента

Клиент регистрируется у владельца как обычно, и в этот же момент бэкенд владельца привязывает его к
партнёру. Партнёр не видит ни одной нашей страницы и не заполняет ни одной формы.

Отличается от уровня 1 тем, что `claim` вызывается с сервера и с токеном: лимита «30 запросов в
минуту с адреса» здесь нет, иначе регистрация массового продукта упрётся в него на тридцатом клиенте.

## Последовательность

```
клиент зарегистрировался у владельца
        │
        ├─ POST /v1/claim          код партнёра + externalAccountId
        │
        └─ POST /v1/partner-link   ссылка партнёра для его же кабинета
```

## Привязка

```bash
curl -X POST https://partna.client.com/v1/claim \
  -H "Authorization: Bearer $BRIDGE_BRIDGE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code": "IRON", "externalAccountId": "user-42"}'
```

Ответ ядра — `{"memberId": "...", "sponsorId": "...", "claimedAt": "..."}`.

Правила, которые уже проверяет ядро:

- повторный `claim` того же клиента возвращает прежнюю привязку, а не ошибку;
- свой код себе привязать нельзя (`400`);
- если у клиента уже другой партнёр — `409`, перепривязки нет;
- если пригласивший заблокирован — `409`;
- окно привязки и allowlist доменов настраиваются в кабинете.

Код партнёра берётся из того, что человек ввёл при регистрации, из cookie `pn_ref` (если он пришёл
через `/r/<код>` моста) или из сохранённого `?ref` в его сессии.

## Ссылка партнёра

```bash
curl -X POST https://partna.client.com/v1/partner-link \
  -H "Authorization: Bearer $BRIDGE_BRIDGE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"externalAccountId": "user-42"}'
```

Ответ: `{"code": "AB12CD", "url": "https://networks.partna.dev/r/AB12CD", "expiresAt": "..."}`.

**Важно.** Поле `url` — адрес ядра. Он приведёт человека на сайт владельца, но cookie моста при этом
не поставит, и привязка развалится. Ссылку, которую владелец даёт партнёру, нужно строить на домене
моста:

```
https://partna.client.com/r/AB12CD
```

`code` из ответа и есть тот код, который нужен для этого адреса.

Ещё три вещи:

- `partner-link` создаёт участника, если его ещё нет, — но корнем, без пригласившего. Поэтому сначала
  `claim`, потом ссылка.
- Каждый вызов `partner-link` выпускает новый код. Сохраните его и показывайте сохранённый, а не
  запрашивайте при каждом открытии страницы.
- `destinationUrl` можно не передавать: подставится `BRIDGE_DESTINATION_URL`.

## Полный пример на бэкенде

```ts
async function onRegistered(user: { id: string }, refCode?: string) {
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${process.env.BRIDGE_TOKEN}`,
  };

  if (refCode) {
    await fetch(`${BRIDGE_URL}/v1/claim`, {
      method: "POST",
      headers,
      body: JSON.stringify({ code: refCode, externalAccountId: user.id }),
    });
  }

  const link = await fetch(`${BRIDGE_URL}/v1/partner-link`, {
    method: "POST",
    headers,
    body: JSON.stringify({ externalAccountId: user.id }),
  }).then((response) => response.json());

  await db.users.savePartnerCode(user.id, link.code);
  return link.code;
}
```

Код партнёра хранится у владельца, поэтому повторная регистрация или вход не создают новых кодов.

## Что владелец получает

В своём кабинете `https://networks.partna.dev/cabinet` он видит партнёров, переходы, клиентов и
начисления. Если ему нужны эти данные в собственном интерфейсе — уровень 4.

## Проверка

```bash
./scripts/smoke.sh --level 2 \
  --url https://partna.client.com \
  --token "$BRIDGE_BRIDGE_TOKEN" \
  --code IRON \
  --user test-42
```

Скрипт сделает `claim` и `partner-link` и покажет, что вернуло ядро. Вызовы реальные: используйте
тестовый код или демо-тенант.

## Частые ошибки

- **`429 too many claims`** — вызов идёт без `Authorization`. Уровень 2 без токена не работает.
- **`400 partner code is missing`** — код не передан и cookie нет.
- **`409` на `claim`** — у клиента уже другой пригласивший. Это решение ядра, обходить его нельзя.
- **Привязка есть, начислений нет** — `memberId` в `order` не совпадает с `externalAccountId` в
  `claim`, либо заказ пришёл за пределами окна привязки.
- **Партнёрская ссылка не ставит cookie** — владелец раздаёт `url` из ответа (домен ядра) вместо
  адреса на домене моста.
