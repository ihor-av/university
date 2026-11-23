import { DurableObject } from 'cloudflare:workers';
import { createModels } from '@earendil-works/pi-ai/models';
import { createRegistry, Harness } from '@earendil-works/pi-durable';
import { PiHarness } from 'agents/harness/pi';
import { Lifecycle } from 'agents/lifecycle';
import { createAI } from 'agents/models/pi-ai';
import { linearTools } from './linear.js';

const team = {
  analyst: { name: 'Аналітик', role: 'аналіз вимог, сценарії та критерії приймання' },
  developer: { name: 'Розробник', role: 'проєктування та пропозиції реалізації' },
  qa: { name: 'Тестувальник', role: 'перевірка вимог, ризики та тестові сценарії' },
};

export class Personnel extends DurableObject {
  ai = createAI({ binding: this.env.AI });
  harness = new PiHarness({
    harness: ({ storage, context, onWake }) => {
      const registry = createRegistry();
      registry.install(linearTools(this.env.LINEAR_KEY));
      const models = createModels();
      models.setProvider(this.ai.provider);
      return Harness.open(storage, { models, registry, onWake }, context);
    },
    defaults: { model: this.ai('@cf/deepseek-ai/deepseek-v4.1-flash-1017'), maxTurns: 5 },
  });
  lifecycle = Lifecycle.install(this).use(this.harness);
  async ask(prompt) {
    const result = await this.harness.prompt(prompt);
    if (result.status !== 'done' || !result.text) throw new Error('Помічник не завершив відповідь');
    return result.text;
  }
}

import { page } from './page.js';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/' && request.method === 'GET') return new Response(page, { headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' } });
    if (url.pathname !== '/api/ask' || request.method !== 'POST') return new Response('Not found', { status: 404 });
    const token = request.headers.get('authorization') || '';
    if (!env.ACCESS_TOKEN || token !== `Bearer ${env.ACCESS_TOKEN}`) return Response.json({ error: 'Невірний ключ доступу' }, { status: 401 });
    if (Number(request.headers.get('content-length') || 0) > 10000) return Response.json({ error: 'Завеликий запит' }, { status: 413 });
    let data;
    try { data = await request.json(); } catch { return Response.json({ error: 'Невірний запит' }, { status: 400 }); }
    if (!Object.hasOwn(team, data.agent) || typeof data.prompt !== 'string' || !data.prompt.trim() || data.prompt.length > 4000) return Response.json({ error: 'Оберіть помічника та введіть завдання до 4000 символів' }, { status: 400 });
    const member = team[data.agent];
    const prompt = `Ти — ШІ-помічник команди проєкту «ЛабЖурнал», ${member.name}. Твоя спеціалізація: ${member.role}. Відповідай українською. Використовуй інструмент Linear для роботи з проєктом за дорученням Ігоря. Не стверджуй, що виконав дії, яких не виконував; рішення приймає керівник проєкту Ігор.\n\nЗавдання: ${data.prompt.trim()}`;
    try { return Response.json({ text: await env.PERSONNEL.getByName(data.agent).ask(prompt) }); }
    catch { return Response.json({ error: 'Не вдалося отримати відповідь помічника. Спробуйте пізніше.' }, { status: 502 }); }
  },
};
