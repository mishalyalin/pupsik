---
name: Always check contact DB before mentioning people
description: CRITICAL rule — before ANY mention of a person, check the SQLite contact DB + ChromaDB semantic search. Never guess who someone is.
type: feedback
originSessionId: af402a5d-8e5c-4048-8728-ad458ef2ad9e
---
ВСЕГДА проверять `~/Desktop/claude/data/contacts.db` и ChromaDB семантический поиск ПЕРЕД тем как:
- Называть, характеризовать или упоминать любого человека в ответе
- Писать письмо / сообщение кому-то
- Готовить call prep или morning briefing
- Отвечать на "кто такой X" / "через кого выйти на Y"

**Why:** Миша 14 Apr 2026 построил SQLite базу (205 контактов, 163 взаимодействия, 98 связей) + ChromaDB семантический поиск (470 документов) + граф связей. Сказал дословно: "ты каждый раз будешь проверять эту базу перед тем, как упоминаются какие-то люди". Без дисциплинированной проверки база превращается в мёртвый груз — смысл её существования в том, что я её использую.

**How to apply:**
1. Первая команда при упоминании человека: `python3 ~/Desktop/claude/tools/memory_search.py search "Name or context" --top 5`
2. Если нужен полный профиль: `python3 ~/Desktop/claude/tools/contacts_db.py find "Name"`
3. Если нужны связи: `python3 ~/Desktop/claude/tools/contacts_db.py graph "Name"` или `chain "A" "B"`
4. НЕ гадать. Если в базе нет — спросить Мишу.
5. После новых важных взаимодействий — обновить interactions в БД и раз в несколько дней переиндексировать ChromaDB (`memory_search.py index`).

Полные инструкции — в CLAUDE.md секция "🔴 MANDATORY: Contact Database Protocol".
