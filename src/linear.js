import { obj, str } from '@earendil-works/pi-schema';

// One unrestricted GraphQL operation, authenticated as the key's owner.
// It must not be replayed automatically: mutations can change or delete data.
export function linearTools(apiKey) {
  return {
    name: 'linear',
    tools: [{
      name: 'linear_graphql',
      description: 'Виконати запит або мутацію GraphQL до Linear. Для невідомих полів можна використати introspection. Зміни виконуються від імені власника ключа.',
      parameters: obj({ query: str() }),
      replay: 'unsafe',
      async execute({ query }, _api, context) {
        if (!apiKey) return { output: [{ type: 'text', text: 'Ключ LINEAR_KEY не налаштовано.' }] };
        try {
          const response = await fetch('https://api.linear.app/graphql', {
            method: 'POST',
            headers: { Authorization: apiKey, 'Content-Type': 'application/json' },
            body: JSON.stringify({ query }),
            signal: context.abortSignal,
          });
          const result = await response.text();
          return { output: [{ type: 'text', text: `HTTP ${response.status}\n${result}` }] };
        } catch {
          return { output: [{ type: 'text', text: 'Запит до Linear перервано або не вдалося виконати. Перевірте стан перед повторенням мутації.' }] };
        }
      },
    }],
  };
}
