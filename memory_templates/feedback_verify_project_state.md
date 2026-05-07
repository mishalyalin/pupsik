---
name: Verify project state before answering
description: 🔴 MANDATORY. Перед любым ответом о статусе проекта/платежа/партнёра - проверить свежую почту (7 дней, все 3 аккаунта) + WA группы. Не полагаться только на CLAUDE.md.
type: feedback
originSessionId: 803b68f6-26d0-46d0-8bfd-59d31802cf6d
---
**Любое утверждение о статусе (открыто/закрыто, оплачено/нет, едет/не едет, ждём/получили) = требует проверки свежих данных перед тем как озвучить.**

**Why:** CLAUDE.md - снимок на момент последнего Last Updated. Между обновлениями почта набирает новые факты: открытые счета, отгрузки с трекингами, платежи, подписанные документы, изменения статусов партнёров. Если отвечать только по CLAUDE.md - я выдаю устаревшую картину как актуальную. Это хуже чем "не знаю" - это дезинформация. 

**How to apply:**

Перед ответом / планом / рекомендацией, который зависит от статуса бизнеса:

1. **Почта - все 3 аккаунта за 7 дней** через `gmail_search_all`:
   - По ключевым партнёрам/темам (your bank, suppliers, freight forwarder, regulator, partners)
   - Искать: "tracking", "invoice", "paid", "shipped", "signed", "confirmed", "verification", "authorized"

2. **WhatsApp группы** `your-company <> partner` - там supply chain переговоры идут чаще чем в email

3. **CLAUDE.md Active Projects / Pending Decisions** - сверить со свежими фактами

4. **Если свежий факт противоречит CLAUDE.md** - обнови CLAUDE.md inline (статус, дата, трекинг, сумма) ДО выдачи ответа. Обнови `## Last Updated`.

5. **Только после этого** - отвечай пользователю с актуальной картиной.

**Шаблоны поиска для быстрого state-refresh:**
- `(your-bank OR paid OR invoice OR payment) after:YYYY/MM/DD`
- `(tracking OR shipped OR shipment OR delivery OR carrier) after:YYYY/MM/DD`
- `(signed OR contract OR agreement OR quotation OR quote) after:YYYY/MM/DD`
- По партнёру: `(from:@domain.com OR to:@domain.com) after:YYYY/MM/DD`

**Исключения:** Если запрос явно не про статус (например "объясни что такое X", "напиши код для Y") - verification не нужен. Но любой план / next steps / "что сейчас происходит" / "что дальше" - ТРЕБУЮТ проверку.
