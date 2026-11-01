# Raivon: Territory Wars — тексты для сторов

> Черновик для Google Play и App Store. Владелец аккаунтов — физлицо (Украина, решение 26). Возрастной рейтинг — 16+ по итоговой анкете (решение 15: кейсы за реальные деньги, мультяшное насилие). Китай не публикуем; RuStore не делаем, в России — без платежей (решение 16). Лимиты длины: название 30, краткое описание Google 80, подзаголовок Apple 30, ключевые слова Apple 100 символов.

## English

**Title (30):** Raivon: Territory Wars

**Subtitle / short description (80):** Grow your realm hex by hex. Win wars, sign peace, redraw the border.

**Apple subtitle (30):** Hex wars. Peace. New borders.

**Keywords (Apple, 100):** strategy,hex,territory,war,empire,kingdom,conquest,map,castle,borders,peace,army,build,clash

**Description:**
Your realm starts as seven hexes and a few huts. Make it an empire.

⚔ REAL-TIME WARS ON A HEX MAP
Drag your armies onto enemy hexes, play war cards — Breakthrough, Airstrike, Encirclement, Defense — and watch the front line move. Cut off supply lines, trap enemies in pockets, take the war goal.

📜 PEACE THAT REDRAWS THE MAP
Occupied land is not yours yet. Win enough war score, choose your demands at the peace table, hold the seal — and watch your glowing border flow over the new land.

🏰 FROM HUTS TO SKYSCRAPERS
Every development level transforms your whole realm: thatched huts become log cabins, stone terems, castles, factories, glass towers and neon skyscrapers. Militia with pitchforks become knights, riflemen, tank crews and power-armoured troopers. Fences become stone walls — and finally the ultra-fence.

💰 BUILD AN ECONOMY
Collect income from every hex, send convoys to golden deposits outlined in yellow, upgrade buildings, research in the Academy, colonize the wild lands.

🛡 YOU NEVER LOSE EVERYTHING
Defeat costs land and loot, never your capital or your progress. Every rival has a leader, a temper and a memory.

Plays offline: no internet connection is needed to play. Contains optional in-app purchases, including random items (loot boxes) with published odds and guarantees.

## Русский

**Название (30):** Raivon: Territory Wars

**Краткое описание (80):** Расширяй державу гекс за гексом. Воюй, заключай мир, двигай границу.

**Подзаголовок Apple (30):** Войны на гексах. Мир. Границы.

**Ключевые слова (Apple, 100):** стратегия,гексы,территория,война,империя,королевство,карта,замок,граница,мир,армия

**Описание:**
Твоя держава начинается с семи гексов и пары халуп. Преврати её в империю.

⚔ ВОЙНЫ В РЕАЛЬНОМ ВРЕМЕНИ
Тяни армии на вражеские гексы, разыгрывай карты войны — Прорыв, Авиаудар, Окружение, Оборону — и смотри, как движется фронт. Режь снабжение, бери врага в котёл, захватывай цель войны.

📜 МИР, КОТОРЫЙ ПЕРЕРИСОВЫВАЕТ КАРТУ
Оккупированная земля ещё не твоя. Набери военный счёт, выбери требования на мирной конференции, удерживай печать — и светящаяся граница перетечёт на новые земли.

🏰 ОТ ХАЛУП ДО НЕБОСКРЁБОВ
Каждый уровень развития меняет всю державу: халупы становятся избами, каменными теремами, замками, фабриками, стеклянными башнями и неоновыми небоскрёбами. Ополченцы с вилами — рыцарями, стрелками, танкистами и штурмовиками в броне. Плетень — каменной стеной и, наконец, ультразабором.

💰 ЭКОНОМИКА
Собирай доход с гексов, отправляй обозы к залежам в жёлтом контуре, улучшай здания, исследуй в Академии, колонизируй дикие земли.

🛡 ВСЁ НЕ ПОТЕРЯТЬ
Поражение стоит земли и добычи, но не столицы и не прогресса. У каждого соседа свой лидер, характер и память.

Играть можно без интернета. Есть необязательные покупки, в том числе случайные предметы (кейсы) с опубликованными шансами и гарантом.

## Анкеты рейтинга (подсказки)
- Насилие: мультяшное, без крови, без реалистичного насилия над людьми.
- Азартные элементы: случайные предметы за реальные деньги (кейсы) — **да**, шансы раскрыты в игре до покупки («i»), есть гарант. Симулированных азартных игр (казино) нет.
- Общение: свободный чат с модерацией появится позже (решение 18) — на запуске отметить по факту включения.
- Реклама: есть (rewarded, interstitial с 3-го дня для неплатящих).
- Сбор данных: см. `privacy_policy.md`.

## Графика

Всё собирается скриптами из моделей игры; после правок моделей или экранов — пересобрать и просмотреть в реальном размере.

| Файл | Размер | Куда | Как собрать |
|---|---|---|---|
| `game/assets/icon/icon_1024.png` | 1024×1024, без альфы | App Store (иконка приложения, `export_presets.cfg` iOS `icons/icon_1024x1024`) | `python3 tools/blender/render_icon.py game/assets/icon` |
| `game/assets/icon/icon_512.png` | 512×512, без альфы | Google Play (иконка карточки), иконка проекта, старая иконка лаунчера Android | там же |
| `game/assets/icon/icon_fg_432.png`, `icon_bg_432.png`, `icon_mono_432.png` | 432×432 | адаптивная иконка Android: передний план (замок в безопасном круге 66 dp), фон (тёплое небо), монохромная для тематических иконок Android 13+ | там же |
| `docs/store/keyart_portrait.png` | 941×1672 | ключевой арт (портрет) | `python3 tools/blender/render_keyart.py R.png` → `python3 tools/ui/compose_keyart.py R.png OUT.png` |
| `game/assets/splash/splash.png` | 941×1672 | заставка запуска: тот же кадр, верх и низ растворяются в цвете фона заставки #080F29 (на телефонах 19.5:9–20:9 полосы над и под ней — часть картинки) | тот же рендер → `compose_keyart.py R.png OUT.png --edge-fade=080F29` |
| `docs/store/feature_graphic.png` | 1024×500, без альфы | Google Play: «Значок для рекомендаций» (feature graphic) | `render_keyart.py R.png 2048 1000 48 --frame=feature` → `compose_keyart.py R.png OUT.png --layout=feature` |
| `docs/store/screens/<набор>_<размер>/<язык>/NN_<сцена>.png` (наборы `play`, `iphone`) | Google Play 1080×1920; iPhone 6.9″/6.7″ 1290×2796 | скриншоты ru и en: карта, бой с картами, мирный договор, церемония, город УР8, альбом командиров | `tools/store_shots.sh` (`--dry-run` покажет вызовы; полный набор ≈ час) |

- Play принимает скриншоты, у которых длинная сторона не больше двух коротких: поэтому 1080×1920 (9:16), а не 1080×2400 современного телефона. App Store Connect требует только 6.9″ (1290×2796 принимается).
- iPad: приложение только для iPhone (`export_presets.cfg` iOS `targeted_device_family=0`; было «iPhone и iPad»). На 3:4 интерфейс, сверстанный под холст 9:16, разъезжается: правая колонка (миникарта, «Фронт/Столица/Форт/Башня») и нижние карточки обрываются посреди экрана (проверка 2026-11-01, кадр 2064×2752). На iPad игра откроется в режиме совместимости с iPhone; скриншотов 13″ не нужно. Набор `ipad` в `tools/store_shots.sh` оставлен для будущей вёрстки под планшет.
- Скриншоты снимать заново после каждого изменения экранов (в частности, после шагов Q1–Q4 второго плейтеста).
- Старые кадры для документации — `docs/screens/` (`tools/godot_shot.sh` с `--demo=…`).
