"""Create course documentation beneath an explicitly shared Notion page."""
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

TOKEN = (pathlib.Path.home() / '.config/labzhurnal/notion-token').read_text().strip()
PAGE_URL = sys.argv[1] if len(sys.argv) > 1 else ''
match = re.search(r'([0-9a-f]{32})(?:[?#]|$)', PAGE_URL.replace('-', ''), re.I)
if not match:
    raise SystemExit('Передайте URL сторінки Notion як аргумент.')
PARENT = match.group(1)
BASE = 'https://api.notion.com/v1/'

def api(method, endpoint, payload=None):
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    request = urllib.request.Request(BASE + endpoint, data=body, method=method, headers={
        'Authorization': 'Bearer ' + TOKEN, 'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json', 'User-Agent': 'LabZhurnal-course/1.0',
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'Notion API: HTTP {error.code}: {error.read().decode()[:500]}') from None

def block(text):
    return {'object': 'block', 'type': 'paragraph', 'paragraph': {
        'rich_text': [{'type': 'text', 'text': {'content': text[:1900]}}]}}

def section(source, start, end):
    return source.split(start, 1)[1].split(end, 1)[0].strip()

report = pathlib.Path('README.md').read_text()
meeting = json.loads(pathlib.Path('assets/meeting.json').read_text())
responses = meeting['participants']
pages = {
    'ЛабЖурнал — проєкт': 'Навчальний проєкт системи лабораторного журналу. Керівник — Авраменко Ігор; три ШІ-помічники виконують дорадчі ролі.\n\nПлан задач і віх: https://linear.app/ihor-av/project/labzhurnal-planuvannya-fdb711cf52dd',
    'Ризики і відповідальність': section(report, '### 1. Реєстр ризиків (Risk Register)', '### 4. Регламент комунікацій'),
    'Комунікації та зустрічі': section(report, '### 4. Регламент комунікацій', '### 5. Простір проєкту та Onboarding-сторінка') + '\n\n' + '\n\n'.join(k + ': ' + v.get('response', '') for k, v in responses.items()),
    'Onboarding — середовище і доступи': 'Проєкт «ЛабЖурнал» є планом, а не реалізованою системою; репозиторій продукту ще не створено.\n\nШІ-помічники розгорнуті на https://labzhurnal-personnel.hackaton-scope-creep.workers.dev/ . Доступ захищений окремим ключем.\n\nДля локальної роботи з наявним кодом помічників: відкрити courses/it-pm/lab4, виконати npm ci, далі npm run check. Для розгортання потрібен авторизований Wrangler і секрети ACCESS_TOKEN та LINEAR_KEY у Cloudflare. Не зберігати секрети в репозиторії.\n\nДошка задач і віх: https://linear.app/ihor-av/project/labzhurnal-planuvannya-fdb711cf52dd . Посилання на репозиторій продукту буде додано, коли його реально створять.\n\nНавчання користувачів: показати створення запису і пояснити, що AI-відповіді є чернетками, які людина перевіряє перед використанням.',
}

existing = {}
cursor = None
while True:
    suffix = f'?page_size=100&start_cursor={cursor}' if cursor else '?page_size=100'
    data = api('GET', f'blocks/{PARENT}/children' + suffix)
    for item in data.get('results', []):
        if item.get('type') == 'child_page': existing[item['child_page']['title']] = item['id']
    if not data.get('has_more'): break
    cursor = data['next_cursor']

for title, content in pages.items():
    if title in existing:
        print('Вже існує, без змін:', title, existing[title])
        continue
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    chunks = [block(p[i:i+1900]) for p in paragraphs for i in range(0, len(p), 1900)]
    page = api('POST', 'pages', {'parent': {'type': 'page_id', 'page_id': PARENT},
        'properties': {'title': {'type': 'title', 'title': [{'type': 'text', 'text': {'content': title}}]}},
        'children': chunks[:100]})
    print('Створено:', title, page['url'])
