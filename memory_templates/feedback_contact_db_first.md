---
name: Always check contact DB before mentioning people
description: CRITICAL rule - before ANY mention of a person, check the SQLite contact DB. Never guess who someone is.
type: feedback
originSessionId: af402a5d-8e5c-4048-8728-ad458ef2ad9e
---
ВСЕГДА проверять `~/Desktop/claude/data/contacts.db` ПЕРЕД тем как:
- Называть, характеризовать или упоминать любого человека в ответе
- Писать письмо / сообщение кому-то
- Готовить call prep или брифинг
- Отвечать на "кто такой X" / "через кого выйти на Y"

**Why:** Миша 14 Apr 2026 построил SQLite базу + граф связей. Сказал дословно: "ты каждый раз будешь проверять эту базу перед тем, как упоминаются какие-то люди". Без дисциплинированной проверки база превращается в мёртвый груз - смысл её существования в том, что я её использую.

**How to apply:**
1. Первая команда при упоминании человека: `python3 ~/Desktop/claude/tools/contacts_db.py find "Name"`
2. Если нужны связи: `python3 ~/Desktop/claude/tools/contacts_db.py graph "Name"` или `chain "A" "B"`
3. НЕ гадать. Если в базе нет - спросить Мишу.
4. После новых важных взаимодействий - добавить их в interactions.

Команды - в CLAUDE.md, секция "Contact DB quick commands".
