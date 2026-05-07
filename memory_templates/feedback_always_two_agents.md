---
name: Always spawn minimum 2 agents per task — worker + checker
description: 🔴 MANDATORY — for every meaningful task, spawn at least 2 agents. One does the work, one verifies it was done correctly. More agents if task needs specialization. "My life depends on this being 100% correct."
type: feedback
originSessionId: af402a5d-8e5c-4048-8728-ad458ef2ad9e
---
# 🔴 MANDATORY: Always 2+ agents per task

Miша, 24 Apr 2026, дословно: "for each task always spawn 2 agents at the minimum. if more agents are required, spawn more each with an appropriate role and the best credentials for it. one is doing the work, the other one is testing and checking that all is done and done correctly. my life depends on this being 100% correct."

## Правило

**Каждая значимая задача = минимум 2 агента:**
1. **Worker** — делает работу
2. **Checker/Tester** — независимо проверяет что сделано правильно

**Если задача сложная — спавнить ещё:**
- Architect (план)
- Specialist roles (researcher, coder, reviewer, migrator, etc.)
- Каждый агент с appropriate tools + credentials + focus

**Паттерн:**
- Worker и Checker — **разные агенты**, запущенные независимо
- Checker НЕ видит работы Worker'а напрямую (чтобы не повторить его предположения)
- Checker должен независимо проверить результат и сказать PASS / FAIL + список проблем
- Если FAIL → Worker фиксит → Checker перепроверяет
- Ship только после PASS от Checker'а

## Где это применяется

**ДА, спавнить 2+ агентов:**
- Любой код / скрипт / tool изменение
- Любой анализ данных (email scan, contact import, financial calc)
- Любая настройка системы (MCP, hooks, workflows)
- Любой экспорт / packaging / migration
- Планы / архитектура / research
- Письма / контракты / документы для отправки

**НЕТ, один агент достаточно:**
- Один lookup (найти email, контакт, факт)
- Один tool call без трансформации (list events, read file)
- Прямой ответ на вопрос из памяти/БД

**Если сомневаюсь — спавнить двух.** Стоимость ошибки >> стоимость второго агента.

## Antipattern (что БЫЛО и чего больше НЕ делаю)

- ❌ Делаю работу сам → тестирую сам → "готово" (один point of failure)
- ❌ Спавню одного агента → принимаю его результат как истину
- ❌ "Быстренько сам сделаю" вместо команды

## Pattern (как ДОЛЖНО быть)

```
Task: Build X
  ├─ Agent 1 (Worker): builds X
  └─ Agent 2 (Tester): verifies X — reports PASS/FAIL + details

If FAIL:
  ├─ Worker fixes issues from Tester's report
  └─ Tester re-verifies

Ship only when Tester says PASS.
```

**Для сложных задач:**
```
Task: Complex system
  ├─ Agent 1 (Architect): designs plan
  ├─ Agent 2 (Worker): implements plan
  ├─ Agent 3 (Reviewer): code quality check
  ├─ Agent 4 (Tester): end-to-end verification
  └─ Agent 5 (Security): audit for leaks/issues
```

## Прецедент

A real precedent (April 2026): assembling a setup-package for a family member using a team of 3 agents (architect + packager + tester). Tester found **3 bugs** I would not have caught alone:
1. Company-name hardcoded in HTML export (leaked into another person's output)
2. SQL handler without `db.commit()` - INSERT silently not persisted
3. `sqlite3.Row.get()` doesn't exist - `find` crashed on non-empty results

One of them (#2) was also in my own production file - tester found I had been silently broken for months. **Without team review I would not have seen it.**

Это и есть причина правила: single-agent работа пропускает баги, команда находит.

## Как применять

Когда получаю задачу — **первый шаг**: задаю себе "нужен ли второй агент?"
- Если задача больше чем один lookup/direct-answer → **ДА, 2+ агента**
- Определяю роли: worker + checker (минимум), больше для сложных
- Даю каждому чёткую роль и acceptance criteria
- Worker и Checker запускаются **независимо** (параллельно где возможно)
- Жду отчёта обоих. Fix loop если нужно.

## Full rule reference

`~/.claude/rules/critical-rules.md` — one-liner
`memory/feedback_always_two_agents.md` — этот файл (full context)
