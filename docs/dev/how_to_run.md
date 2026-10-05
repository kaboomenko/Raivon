# Как запускать (для автономной разработки)

1. `tools/setup_env.sh` — восстановить инструменты в новом контейнере (Godot 4.5.1, Blender bpy 5.0.1, Xvfb + Mesa lavapipe, npm).
2. Модели: `python3 tools/blender/export_assets.py game/assets/models [имя ...]` → `.glb` для Godot.
3. Импорт в Godot: `/opt/godot/Godot_v4.5.1-stable_linux.x86_64 --headless --path game --import`.
4. Скриншот клиента: `tools/godot_shot.sh /путь/out.png [--zoom=0.15]` (941×1672, как эталон).
5. Проверка GDScript: `godot --headless --path game --check-only --script res://scripts/<file>.gd`.
6. Старый веб-прототип (`apps/client`, `packages/sim`) — только как справочник правил; `npm test` гоняет тесты sim.

Особенности: видеокарты нет, рендер программный (lavapipe) — кадр 941×1672 рендерится ~30 с. Сайты с CC0-моделями заблокированы сетевой политикой окружения.
