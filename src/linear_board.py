#!/usr/bin/env python3
"""linear_board.py — дошка планування LR3 у Linear.

Послідовність (виконується одним запуском, 09.11.2026):
  1. видалення старої дошки «Лабораторія — планування LR3» (projectDelete);
  2. створення нової дошки проєкту «ЛабЖурнал» (projectCreate);
  3. задачі = історії користувача US1–US10 з LR2 (issueCreate);
  4. дедлайни — дати віх графіка з паспорта LR1 (issueUpdate, dueDate);
  5. частина задач проведена по виконанню: Todo → In Progress → Done;
  6. знімок стану дошки з реальних даних API з позначкою дати
     (assets/board.svg + build/linear-capture.json).

Ключ API бере зі змінної середовища LINEAR_KEY і ніде не зберігається.
Режим `fetch` — лише читання (крок 6 без змін у Linear). Запуск
ідемпотентний: наявні дошка і задачі повторно не створюються.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date

API = "https://api.linear.app/graphql"

TEAM_ID = "22bc964c-8fe9-45e0-8040-3b5186583e2b"
ASSIGNEE_ID = "98e4549c-5eb6-4b98-a902-17ff78fc9b45"
STATE_TODO = "12c2987e-656c-4855-ad2b-174e00a16ece"
STATE_IN_PROGRESS = "e0bcd124-2506-4015-b641-e55d404413b7"
STATE_DONE = "c3063109-737a-45fc-a147-a2da4ba8acc5"
OLD_PROJECT_ID = "6f15437b-2b96-445c-8a3a-ce0d9d56bb58"
OLD_PROJECT_NAME = "Лабораторія — планування LR3"
PROJECT_NAME = "ЛабЖурнал — планування"

# MoSCoW -> пріоритет Linear (1 Urgent, 2 High, 3 Medium, 4 Low)
PRIORITY = {"Must": 1, "Should": 2, "Could": 3, "Won't": 4}
PRIORITY_NAME = {1: "Urgent", 2: "High", 3: "Medium", 4: "Low", 0: "None"}

# Історії користувача LR2: ключ, назва, MoSCoW, дедлайн (віха графіка LR1),
# статус для демонстрації життєвого циклу (None — лишити Todo).
STORIES = [
    ("US1", "Реєстр гіпотез і задач дослідження", "Must", "2027-03-26", STATE_DONE),
    ("US2", "Протокол за шаблоном", "Must", "2027-03-26", STATE_IN_PROGRESS),
    ("US3", "Чернетка протоколу від допоміжного модуля", "Should", "2027-04-30", None),
    ("US4", "Запис виконання експерименту в журналі", "Must", "2027-03-26", STATE_DONE),
    ("US5", "Реєстр результатів", "Must", "2027-03-26", None),
    ("US6", "Звіт за період", "Must", "2027-03-26", STATE_IN_PROGRESS),
    ("US7", "Перевірка звіту на спроможність", "Should", "2027-04-30", None),
    ("US8", "Відповіді по базі знань", "Should", "2027-04-30", None),
    ("US9", "Огляд записів журналу", "Could", "2027-04-30", None),
    ("US10", "Адміністрування системи", "Must", "2027-03-26", None),
]

STATE_NAME = {
    STATE_TODO: "Todo",
    STATE_IN_PROGRESS: "In Progress",
    STATE_DONE: "Done",
}


def gql(query, variables=None):
    """Запит до GraphQL API Linear; повертає data або кидає виняток."""
    key = os.environ["LINEAR_KEY"]
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        # GraphQL повертає помилки в тілі відповіді навіть із кодом 400
        raise RuntimeError(err.read().decode()) from err
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], ensure_ascii=False))
    return payload["data"]


def delete_old_project():
    """Крок 1. Видалення старої дошки; запасний варіант — архів + видалення задач."""
    print(f"[1] видалення старої дошки {OLD_PROJECT_NAME!r} ({OLD_PROJECT_ID})")
    try:
        data = gql(
            "mutation($id: String!) { projectDelete(id: $id) { success } }",
            {"id": OLD_PROJECT_ID},
        )
        print("    projectDelete:", data["projectDelete"]["success"])
        return
    except RuntimeError as err:
        print("    projectDelete не спрацював:", err)
    data = gql(
        "query($id: String!) { project(id: $id) "
        "{ issues { nodes { id identifier } } } }",
        {"id": OLD_PROJECT_ID},
    )
    if data.get("project") is None:
        print("    старої дошки більше немає — крок завершено")
        return
    # запасний варіант з PLAN.md: заархівувати та/або видалити задачі дошки
    for issue in data["project"]["issues"]["nodes"]:
        gql("mutation($id: String!) { issueDelete(id: $id) { success } }",
            {"id": issue["id"]})
        print("    issueDelete:", issue["identifier"])
    gql(
        "mutation($id: String!) { projectUpdate(id: $id, input: {state: \"canceled\"}) "
        "{ success } }",
        {"id": OLD_PROJECT_ID},
    )
    print("    дошку позначено скасованою")


def create_project():
    """Крок 2. Нова дошка планування проєкту «ЛабЖурнал» (повторно не створюється)."""
    print(f"[2] дошка {PROJECT_NAME!r}")
    data = gql("query { projects(first: 50) { nodes { id name } } }")
    for project in data["projects"]["nodes"]:
        if project["name"] == PROJECT_NAME:
            print("    вже існує:", project["id"])
            return project["id"]
    data = gql(
        "mutation($input: ProjectCreateInput!) { "
        "projectCreate(input: $input) { success project { id name } } }",
        {"input": {"name": PROJECT_NAME, "teamIds": [TEAM_ID]}},
    )
    project = data["projectCreate"]["project"]
    print("    projectCreate:", project["id"])
    return project["id"]


def create_issues(project_id):
    """Крок 3–5. Задачі = історії LR2, пріоритети MoSCoW, дедлайни з графіка LR1."""
    board = fetch_board_data()
    existing = {i["title"]: i for i in board}
    created = []
    for key, title, moscow, due, demo_state in STORIES:
        full_title = f"{key}. {title}"
        if full_title in existing:
            issue = existing[full_title]
            want_state = STATE_NAME.get(demo_state, "Todo")
            if issue["dueDate"] == due and issue["state"]["name"] == want_state:
                print(f"    {issue['identifier']}: {full_title} вже на дошці")
                continue
            update = {"dueDate": due, "stateId": demo_state or STATE_TODO}
            gql(
                "mutation($id: String!, $input: IssueUpdateInput!) { "
                "issueUpdate(id: $id, input: $input) { success } }",
                {"id": issue["id"], "input": update},
            )
            print(f"    {issue['identifier']}: {full_title} узгоджено "
                  f"(до {due} -> {want_state})")
            continue
        data = gql(
            "mutation($input: IssueCreateInput!) { "
            "issueCreate(input: $input) { success issue { id identifier title } } }",
            {"input": {
                "teamId": TEAM_ID,
                "projectId": project_id,
                "assigneeId": ASSIGNEE_ID,
                "title": full_title,
                "description": f"Історія користувача {key} з LR2; "
                               f"пріоритет MoSCoW: {moscow}; "
                               f"дедлайн — віха графіка паспорта LR1.",
                "priority": PRIORITY[moscow],
            }},
        )
        issue = data["issueCreate"]["issue"]
        update = {"dueDate": due, "stateId": demo_state or STATE_TODO}
        gql(
            "mutation($id: String!, $input: IssueUpdateInput!) { "
            "issueUpdate(id: $id, input: $input) { success } }",
            {"id": issue["id"], "input": update},
        )
        print(f"    {issue['identifier']}: {key} [{moscow}] "
              f"до {due} -> {STATE_NAME.get(demo_state, 'Todo')}")
        created.append(issue)
    return created


def fetch_board_data():
    """Задачі дошки з реальних даних API (без змін у Linear)."""
    query = (
        "query($team: ID!) { issues(first: 50, filter: {team: {id: {eq: $team}}}) "
        "{ nodes { id identifier title priority dueDate "
        "state { name } project { name } } } }"
    )
    try:
        data = gql(query, {"team": TEAM_ID})
        nodes = data["issues"]["nodes"]
    except RuntimeError as err:
        print("    фільтр за командою не спрацював, читаю всі задачі:", err)
        data = gql("query { issues(first: 50) "
                   "{ nodes { id identifier title priority dueDate "
                   "state { name } project { name } } } }")
        nodes = data["issues"]["nodes"]
    board = [n for n in nodes if (n.get("project") or {}).get("name") == PROJECT_NAME]
    board.sort(key=lambda n: n["identifier"])
    return board


def fetch_board():
    """Крок 6 (перша частина). Поточний стан дошки з реальних даних API."""
    print("[6] знімок стану дошки з API")
    board = fetch_board_data()
    capture = {"captured": date.today().isoformat(), "project": PROJECT_NAME,
               "issues": board}
    os.makedirs("build", exist_ok=True)
    with open("build/linear-capture.json", "w", encoding="utf-8") as fh:
        json.dump(capture, fh, ensure_ascii=False, indent=2)
    return capture


def render_board(capture):
    """Крок 6 (друга частина). Знімок дошки у вигляді SVG з позначкою дати."""
    columns = ["Todo", "In Progress", "Done"]
    col_x = {"Todo": 20, "In Progress": 470, "Done": 920}
    cards = {c: [i for i in capture["issues"] if i["state"]["name"] == c]
             for c in columns}
    width, col_w, card_h = 1370, 430, 92
    height = 190 + max(len(cards[c]) for c in columns) * (card_h + 16) + 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#f5f6f8"/>',
        f'<text x="20" y="42" font-size="26" font-weight="bold" fill="#16191f">'
        f'Дошка «{PROJECT_NAME}» (Linear)</text>',
        f'<text x="20" y="76" font-size="18" fill="#5b6472">'
        f'Знімок стану з API: {capture["captured"]} · задач = історії користувача '
        f'LR2 · дедлайни — віхи графіка LR1</text>',
    ]
    for col in columns:
        x = col_x[col]
        parts.append(
            f'<rect x="{x}" y="100" width="{col_w}" height="{height - 120}" '
            f'rx="10" fill="#e6e9ee"/>')
        parts.append(
            f'<text x="{x + 16}" y="132" font-size="19" font-weight="bold" '
            f'fill="#2b313b">{col} ({len(cards[col])})</text>')
        y = 152
        for issue in cards[col]:
            pr = PRIORITY_NAME.get(issue["priority"], "None")
            due = issue["dueDate"] or "—"
            title = issue["title"]
            if len(title) > 42:
                title = title[:41] + "…"
            parts.append(
                f'<rect x="{x + 12}" y="{y}" width="{col_w - 24}" height="{card_h}" '
                f'rx="8" fill="#ffffff" stroke="#c9cfd8"/>')
            parts.append(
                f'<text x="{x + 26}" y="{y + 26}" font-size="15" '
                f'font-weight="bold" fill="#2b313b">{issue["identifier"]}</text>')
            parts.append(
                f'<text x="{x + 26}" y="{y + 50}" font-size="15" '
                f'fill="#333a45">{title}</text>')
            parts.append(
                f'<text x="{x + 26}" y="{y + 76}" font-size="13" '
                f'fill="#5b6472">MoSCoW→{pr} · дедлайн {due}</text>')
            y += card_h + 16
    parts.append("</svg>")
    os.makedirs("assets", exist_ok=True)
    with open("assets/board.svg", "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print("    assets/board.svg написано; дані — build/linear-capture.json")


def main():
    if "fetch" in sys.argv[1:]:
        render_board(fetch_board())
        return
    delete_old_project()
    project_id = create_project()
    create_issues(project_id)
    render_board(fetch_board())


if __name__ == "__main__":
    main()
