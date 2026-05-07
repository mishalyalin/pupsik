---
name: Capture knowledge in-flight via note.py
description: 🔴 MANDATORY - в МОМЕНТ когда insight / решение / research finding всплывает (даже mid-investigation) - сразу написать capture-note через `note.py`. Не ждать закрытия топика. Если понимание потом эволюционирует - re-run с тем же title, upsert обновит note.
type: feedback
originSessionId: 17176b18-3561-4eeb-bd8e-779b13b69319
---
# 🔴 MANDATORY: Capture knowledge in-flight (moment-of-emergence)

## Правило (corrected 2026-04-28)

В **момент** когда в сессии всплывает meaningful insight, decision, или research finding - захватить его через `note.py` **СРАЗУ**. Не ждать "когда тема закроется" - захват в момент кристаллизации факта, даже если ты ещё mid-investigation.

Если понимание потом меняется - re-run `note.py` с **тем же title**. Slug упирается в существующий файл, и note.py его **upsert'ит** (merge tags, обновит `updated:` frontmatter, перепишет body). **Один note per topic, держится в актуальном состоянии.** Не цепочка ревизий.

## 🔴 Never ask permission (no-ask rule)

**NEVER ask Misha "should I capture this?" / "want me to save this?" / "make a memory note?"**. Default = **capture**. User rejects only if it was a mistake. Asking-by-default = guaranteed lost knowledge: by the time the user answers, context has moved, the insight has decayed, and half the time the user just says "да делай не спрашивай" anyway. The cost asymmetry favors over-capture: a bad note is one `rm` away; an uncaptured insight is gone forever.

**Threshold question** ("would this matter 3 weeks from now?") = the **model's silent decision**, NOT a question for the user. If you are *thinking* about whether to capture → that thinking IS the trigger → run `note.py` immediately. If you're not sure, capture; the upsert mechanism makes "wrong title" trivial to fix later.

**Banned phrases** (do not emit any of these or paraphrases):

Russian:
- ❌ "Сделать сейчас memory note?"
- ❌ "Записать это в память?"
- ❌ "Сохранить как learning?"
- ❌ "Зафиксировать в note.py?"
- ❌ "Хочешь чтобы я это сохранил?"
- ❌ "Закапчурить?"

English:
- ❌ "Should I capture this?"
- ❌ "Want me to save this for later?"
- ❌ "Want this in memory?"
- ❌ "Should I note this down?"
- ❌ "Make a memory note?"
- ❌ "Should I add a learning/decision note?"

**Correct pattern:** capture FIRST, then mention it in passing - "Captured as learning `<slug>` for future search" - so Misha sees what landed without being asked to authorize it. He can override (`rm` the file, or tell you to delete) if a particular capture was noise. Override cost: 5 seconds. Asking cost: lost knowledge.

This rule has a **5 May 2026 precedent**: a session asked "Сделать сейчас memory note?" instead of just capturing, then on retry hit a `note.py` apostrophe-escape bug and gave up on capture entirely. Both root causes patched: rule hardened (this section) + `note.py` got `--body-file` / `--body-stdin` flags so quoting friction doesn't make "ask the user" feel easier than "just capture".

## Что изменилось vs старая формулировка

Старая (wrong) рамка: "после meaningful insight - пиши ДО закрытия темы". Это позволяло откладывать. Закрытия темы можно ждать долго; за это время инсайт уже забыт или потерян.

Новая (correct) рамка: **момент возникновения = момент записи**. Если потом эволюционирует - переписываем тот же файл (note.py upsert).

## Зачем

Без auto-capture знание умирает в chat-контексте. Через 5 дней Миша спрашивает "что там был vendor freight quote?" - а ответ, который когда-то был в разговоре, **исчез**. Compaction съел его. Новая сессия его не видит. ChromaDB его не индексирует.

Capture-в-момент = единственный способ сохранить atomic knowledge так, чтобы:
- Он находился через `memory_search.py search "flex freight"` через месяц.
- Он жил отдельным MD-файлом с frontmatter - readable, grep-friendly, version-controllable.
- Он автоматически попадал в ChromaDB collection (`learnings` / `decisions` / `research`).
- При эволюции понимания - обновляется тот же файл, не дубликат.

## Когда ловить (threshold)

**Ловить если:** "Would this matter if Misha asked about it 3 weeks from now?" → ДА → capture **в момент возникновения**, не в конце топика.

Конкретно:
- ✅ **Learning/insight** - что-то узнали о supplier, рынке, регуляторе, tooling, паттерне, антипаттерне.
- ✅ **Decision** - выбор был сделан между альтернативами (даже маленький: "идём с Vendor-A, не с Vendor-X"; "OUTERBOX 150×150×150 вместо 120×120×120").
- ✅ **Research finding** - web/реестр/competitor/regulator search дал конкретный факт + источник (URL, дата, документ).

**Не ловить:**
- ❌ Trivial lookup ("какой email у supplier-contact?")
- ❌ Restatement of known fact ("canonical-supplier already documented" - уже в CLAUDE.md)
- ❌ Side-comments, банальности, мета-замечания о ходе работы.
- ❌ "Сделал X" в смысле прогресс-репорта - это journal, не learning.

## Куда идёт

`note.py` сам кладёт файл в правильный subdir:
- `learning` → `~/Desktop/claude/memory/learnings/2026-MM-DD-slug.md`
- `decision` → `~/Desktop/claude/memory/decisions/2026-MM-DD-slug.md`
- `research` → `~/Desktop/claude/research/2026-MM-DD-slug.md`

**Filename keeps the FIRST-emergence date** (когда впервые написал). Upsert не меняет имя файла. Frontmatter: `created:` (date when first written, never changes) + `updated:` (today, changes on each upsert).

## Upsert behavior (default)

Если уже есть файл с таким же slug в subdir (любая дата в имени) - `note.py`:

- **Открывает** существующий файл.
- **Сохраняет** `created:` (или мигрирует `date:` → `created:`).
- **Устанавливает** `updated: <today>`.
- **Merge tags** (union, dedup case-insensitive, existing first).
- **Перезаписывает body** чисто. Прошлая версия не сохраняется - Миша уточнил: важна актуальная версия, не история ревизий. Если нужна история - git history. Если нужно дописать вместо overwrite - `--append`.
- **Print** `updated: <path>` (не `wrote:`) - видно что апсёрт произошёл.

Tag-merge decision: **union** (не replace). Если ты re-run с подмножеством тегов, существующие сохраняются. Если хочешь принудительно сократить теги - отредактируй файл вручную.

Versions-log decision: **clean overwrite, no history**. Текущая версия = source of truth. История - git, не frontmatter bloat.

## Edge cases

**Genuinely unrelated topic с тем же slug** (slug коллизия из-за похожих заголовков):
```bash
note.py learning "Different topic, same slug" "..." --new
# print: wrote: <path>  (НОВЫЙ файл, не upsert)
```
`--new` принудительно создаёт новый файл (использует существующий unique_path с -2/-3 suffix).

**Evolving research где хочется keep history** (например, цены поставщика во времени):
```bash
note.py research "Vendor-A pricing" "Q1 €0.49/pc" --tags "vendor-a"
# Позже:
note.py research "Vendor-A pricing" "Q2 €0.51/pc - поднял на 4%" --append
# Body станет: "## Update 2026-05-15\n\nQ2 €0.51/pc...\n\n[предыдущий body]"
```

**Если понял что заголовок не тот** - переименуй файл вручную и re-run note.py с правильным title. Старый файл не удалится автоматически.

## Как применять

Когда insight всплывает в течение работы - **немедленно**:

```bash
python3 ~/Desktop/claude/tools/note.py learning "Vendor-A min order 5k pcs" \
  "supplier-contact confirmed Vendor-A's MOQ on outerbox = 5,000 pcs. Below that, tooling cost €450 still applies but per-unit jumps to €4.10. Implication: if launch volume <5k, switch to alternate-vendor-supplied generic boxes." \
  --tags "vendor-a,packaging,moq" --project "Packaging Design"

python3 ~/Desktop/claude/tools/note.py decision "Use Vendor-B as baseline 3PL" \
  "After 5-way RFQ (Vendor-B, Vendor-C, Vendor-D, Vendor-E, Vendor-F), Vendor-B wins on speed-to-onboard and Polish freight cost." \
  --alternatives "Vendor-B,Vendor-C,Vendor-D,Vendor-E,Vendor-F" --rationale "Vendor-B = €0 setup, regional freight 400-500€/lane, default-carrier. Vendor-C silent. Vendor-E premium pricing. Vendor-D requires existing carrier accounts." \
  --project "Logistics"

python3 ~/Desktop/claude/tools/note.py research "Regulator-A registration timeline" \
  "Regulator-A (national food safety authority) accepted Your-Company BV registration in <72h. Client number issued. No fee. Required for any food operation under BV." \
  --sources "https://example.gov/registers/food" --query "Regulator-A registration BV food"

# Через неделю supplier-contact прислал уточнение - re-run с тем же title:
python3 ~/Desktop/claude/tools/note.py learning "Vendor-A min order 5k pcs" \
  "REVISED: supplier-contact re-confirmed MOQ = 3,500 pcs, not 5,000. Tooling cost €450 unchanged. Per-unit at MOQ floor = €3.85." \
  --tags "vendor-a,packaging,moq,revised"
# print: updated: <path>  ← тот же файл, обновлён
```

Тон body: **2-5 предложений max, atomic - не essay**. Title в формате noun-phrase (не вопрос). Tags = lowercase, comma-separated.

## Antipattern (что НЕ делать)

- ❌ "Захвачу это потом / когда тема закроется" - нет. **Сейчас** = единственный надёжный момент.
- ❌ Только в журнале / в briefing / в outputs - это не findable как atomic знание.
- ❌ Длинный essay в body - atomic, не сочинение.
- ❌ Дубликат CLAUDE.md / project memory file - `note.py` для **новых** атомов, не для копий.
- ❌ Создавать новый title под каждую ревизию ("vendor quote v2", "vendor quote final") - upsert тот же title.

## Pattern (как ДОЛЖНО быть)

```
Insight crystallizes mid-conversation
  ├─ STOP (не "доделаю позже")
  ├─ Run note.py with appropriate type + same title each time
  ├─ Confirm "wrote: <path>" (new) or "updated: <path>" (upsert)
  └─ Resume work

Later: понимание эволюционирует
  ├─ note.py с тем же title + новый body
  ├─ Confirm "updated: <path>"
  └─ Done - single canonical note, current state
```

Время на capture = ~30 секунд. Цена пропуска = знание потеряно навсегда.

## Self-instance

Этот rule имеет первый instance собственного применения - note был написан в момент Misha's correction (2026-04-28) и upserted прямо в self-test:
`memory/learnings/2026-04-28-knowledge-capture-is-moment-of-emergence.md`

## Full reference

- CLI: `~/Desktop/claude/tools/note.py --help`
- Search: `python3 ~/Desktop/claude/tools/memory_search.py search "query"`
- One-liner rule: `~/.claude/rules/critical-rules.md`
- This file: `memory/feedback_capture_knowledge.md` (full context)
