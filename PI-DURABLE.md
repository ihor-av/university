# Pi Durable: ШІ-помічники проєкту «ЛабЖурнал»

Цей файл пояснює код у `src/`, який перетворює три ролі проєктної команди
на робочих ШІ-помічників. Помічники — не окремі люди й не окремі облікові
записи: це програмні засоби, які готують пропозиції, а рішення ухвалює
керівник проєкту.

## Що таке Pi Durable

**Pi Durable** — бібліотека для побудови агентів, чий стан розмови
зберігається між запитами. Кожен помічник живе у власному **Durable Object**
на Cloudflare Workers: об'єкт пам'ятає історію діалогу, інструменти й стан
навіть після перезапуску Worker. Модель викликається через прив'язку
Workers AI, а не через окремий API-ключ у коді.

У цьому проєкті використано:

- `@earendil-works/pi-durable` — `Harness`, `createRegistry`;
- `agents/harness/pi` — `PiHarness`, обгортка для Cloudflare Agents;
- `agents/lifecycle` — життєвий цикл Durable Object;
- `@earendil-works/pi-ai/models` — реєстр моделей і провайдер Workers AI;
- `@earendil-works/pi-schema` — опис параметрів інструментів.

## Архітектура

```
Браузер
  │  POST /api/ask  { agent, prompt }
  │  Authorization: Bearer <ACCESS_TOKEN>
  ▼
Cloudflare Worker (src/index.js)
  ├─ перевіряє ключ, розмір запиту й назву ролі
  ├─ додає до промпту роль і правила поведінки
  └─ env.PERSONNEL.getByName(agent).ask(prompt)
        │
        ▼
Durable Object «Personnel» (окремий для analyst / developer / qa)
  ├─ PiHarness зберігає історію в SQLite Durable Object
  ├─ модель: @cf/deepseek-ai/deepseek-v4.1-flash-1017
  └─ інструмент linear_graphql (src/linear.js)
        │
        ▼
Linear GraphQL API
```

Три ролі задані в `src/index.js`:

| Ключ | Роль | Призначення |
|---|---|---|
| `analyst` | Аналітик | аналіз вимог, сценарії, критерії приймання |
| `developer` | Розробник | проєктування та пропозиції реалізації |
| `qa` | Тестувальник | перевірка вимог, ризики, тестові сценарії |

## Карта коду

| Файл | Що робить |
|---|---|
| `src/index.js` | Worker, авторизація, маршрут `/api/ask`, клас `Personnel`, `PiHarness` |
| `src/linear.js` | інструмент `linear_graphql` для запитів і мутацій Linear |
| `src/page.js` | простий HTML-інтерфейс для надсилання завдання помічнику |
| `wrangler.jsonc` | прив'язки `AI`, `PERSONNEL`, міграція Durable Object |
| `package.json` | залежності та команди `check` / `deploy` |

## Життєвий цикл запиту

1. Користувач відкриває сторінку, вводить ключ доступу, обирає роль і
   формулює завдання.
2. Worker перевіряє `Authorization: Bearer <ACCESS_TOKEN>`, обмежує розмір
   запиту й перевіряє, що роль існує.
3. До промпту додається системна частина: хто цей помічник, що він
   відповідає українською, що він не має вигадувати виконані дії й що останнє
   рішення — за керівником проєкту.
4. `env.PERSONNEL.getByName(agent)` бере Durable Object саме цієї ролі.
5. `PiHarness.prompt()` веде цикл «модель → виклик інструмента → модель»,
   зберігаючи історію в SQLite Durable Object.
6. Якщо модель викликає `linear_graphql`, інструмент робить запит до
   `https://api.linear.app/graphql` з ключем `LINEAR_KEY`.
7. Відповідь повертається браузеру як `{ "text": "..." }`.

## Безпека

- `ACCESS_TOKEN` і `LINEAR_KEY` — секрети Cloudflare, не файли репозиторію.
- Ключ доступу перевіряється на кожному запиті; без нього — `401`.
- Розмір запиту обмежений 10 000 байт, промпт — 4 000 символів.
- Інструмент Linear позначений `replay: 'unsafe'`: після обриву запиту
  мутація не повторюється автоматично, щоб не змінити дані двічі.
- Помічники не мають доступу до репозиторію продукту й не можуть
  затверджувати рішення за людину.
- Відповіді моделі вважаються **чернетками**; науковець перевіряє їх перед
  використанням.

## Локальний запуск і розгортання

```bash
cd lab4
npm ci
npm run check          # перевірка збірки без публікації
npx wrangler secret put ACCESS_TOKEN
npx wrangler secret put LINEAR_KEY
npm run deploy
```

Після розгортання адреса Worker'а відкриває сторінку команди. Ключ
`ACCESS_TOKEN` вводиться на сторінці, у репозиторії його немає.

## Джерела

- Cloudflare Agents: Pi harness — <https://developers.cloudflare.com/agents/harnesses/pi/>
- Earendil: Pi Durable — <https://earendil.com/posts/pi-durable/>
