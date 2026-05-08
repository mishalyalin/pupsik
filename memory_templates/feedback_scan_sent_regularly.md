---
name: Scan all inbound/outbound channels regularly during active sessions
description: 🔴 MANDATORY. Scan regularly during active sessions — Gmail sent + inbox (all configured accounts) + WhatsApp (DMs + groups). Every 1-2 hours / before proposing actions / when user references something. The user acts in parallel everywhere.
type: feedback
---
**В любой активной session регулярно сканировать ВСЕ каналы — sent, inbox, WhatsApp. Не только sent.**

**Why:** the user runs business in parallel — отправляет vendor responses, supplier messages в WA groups, делает quick decisions сам. Если ты не sync с inbound + outbound + WA, ты working from stale context и предлагаешь устаревшие actions. Хуже того — можешь предложить отправить email кому пользователь уже написал 5 минут назад.

**How to apply:**

### Gmail — ВСЕ настроенные аккаунты

Use `gmail_search_all` (multi-gmail MCP) с queries:
- **Sent:** `in:sent newer_than:1d -category:promotions`
- **Inbox:** `newer_than:1d -category:promotions -category:social -in:sent`
- По партнёру: `from:vendor@domain.com OR to:vendor@domain.com newer_than:2d`

### WhatsApp — MANDATORY каждый active session

Process:
1. `whatsapp_sync_to_contacts_db` с `since: '2 days ago'` (or longer if session inactive)
2. `whatsapp_list_chats` с `onlyBusinessContacts: true`, `includeGroups: true`, `since: '2 days ago'`
3. Для каждой активной business group → `whatsapp_messages_with` с последними 20 сообщениями
4. Critical groups: те что названы по pattern `<your-company> <> <partner>` — supply chain переговоры идут там

### When to scan:

- В начале любой session после первого user message
- 🔴 **STRICT: ПЕРЕД любым proposed action (draft / reply / plan / "что дальше") — scan sent last 30 min FIRST.** Non-negotiable. Как git pull before push. Пользователь чаще всего уже написал то что ты хочешь предлагать.
- Каждые 1-2 часа активной работы (passive sync)
- При переключении темы
- Когда user references "я уже написал / получил / увидел X" — confirm + update memory

### 🔴 Final sent re-scan invariant (для long-running compose flows)

Если ты генеришь morning briefing / status report / любой output, который занимает >5 минут от data-gather до compose — **обязательно re-scan `in:sent newer_than:6h` ПРЯМО перед публикацией**.

Diff против initial gather:
- Любой новый message = пользователь отправил пока ты compose-ил
- Особенно важно: outbound к партнёрам в ESCALATED block, gov/regulator, hard-deadline items

Если найден новый sent message:
1. Прочитать полный body (`gmail_read_message`)
2. Update escalation tracker / state file `last_action`
3. Если item был "silent N days" → поменять формулировку на "just pinged [time] with [frame]"
4. Обновить project memory inline если фактическое состояние сменилось
5. Если новый sent добавил hard-deadline frame → повысить urgency в output

Skip только если data-gather был <5 min назад.

### How to use findings:

- Новые факты → обновить project memory (e.g. CLAUDE.md) inline
- Decisions пользователь принял solo → log с timestamp
- Supplier responses → update project_*.md + contacts.db interactions
- Scale-up plans / new orders → update relevant project memory

### Critical: не предлагать действие если пользователь уже сделал

- Проверить что не пишешь draft email к vendor кому пользователь уже написал сегодня
- Не дублировать questions про темы которые в inbox уже имеют ответ
- Не противоречить решениям из WA групп

**Integration:** это superset для `feedback_verify_project_state.md` (проверять перед ответом о status). Если есть отдельное feedback правило про business-specific WA groups — это ему совместимо, не заменяет.
