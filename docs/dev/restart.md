# Продолжение после перезапуска контейнера

Длинные работы идут воркфлоу (агенты: исполнитель → ревизор → исправление). Контейнер может перезапуститься — тогда:

1. Закоммитить и запушить рабочее дерево как есть (частичные правки прерванных агентов).
2. Посмотреть журналы прерванных воркфлоу: `/root/.claude/projects/-home-user-Raivon/<сессия>/subagents/workflows/wf_*/journal.jsonl` — строки `started`/`result` с `label` вида `P5:fix`, `s05_hex_action:review`. Прерванный агент — `started` без `result`.
3. Собрать результаты всех агентов в `scratchpad/resume_args.json` (ключи `<label с ':' → '_'>`, например `P5_impl`, `P5_review`).
4. Запустить продолжение без правки скриптов, только аргументами:
   - мир: `tools/workflows/soft_continue.js` с `{"lanes": [[{"id":"P5","start":"fix"}, {"id":"P6"}, …], [{"id":"B2","start":"review"}, …]], "phases": ["Map","Models"], "final": "F1"}`;
   - интерфейс: `tools/workflows/ui_continue.js` с `{"lanes": [[{"id":"s05_hex_action","start":"review"}, {"id":"s06_war_screens"}, …]], "phases": ["Screens"]}`.
   `start`: `impl` (по умолчанию), `review` (исполнитель закончил — отчёт берётся из `<id>_impl`), `fix` (ревизор закончил — замечания из `<id>_review`).

`resumeFromRunId` для параллельных очередей не годится: кэш берётся по префиксу порядка вызовов, а у параллельных очередей порядок плавает, и уже сделанные шаги запускаются заново.

Шаги и полные инструкции: мир — `docs/dev/soft_style_plan.json`, интерфейс — `docs/dev/ui_plan.json`.
