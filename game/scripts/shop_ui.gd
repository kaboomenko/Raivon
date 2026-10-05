extends Control
## «Лавка» — the store sheet (canon §15.3–15.5): cases with odds («i») and pity counters, Raivite SKUs,
## packs and the Atelier. Purely a view: purchases and openings are requested through signals and the
## controller (main.gd) applies them. Payments are stubs until the store SDKs are connected.

signal open_case(case_id: String, times: int, pay: String)  # pay: "free" | "raivite" | "ad"
signal buy_sku(sku: String)
signal closed

const GameUI := preload("res://scripts/game_ui.gd")
const MUTED := Color(0.62, 0.68, 0.78)
const VW := 941.0
const VH := 1672.0
const RARITY_COLOR := {"common": Color(0.75, 0.78, 0.82), "rare": Color(0.35, 0.6, 1.0), "epic": Color(0.7, 0.4, 1.0), "legendary": Color(1.0, 0.75, 0.2)}
const RARITY_RU := {"common": "Обычное", "rare": "Редкое", "epic": "Эпическое", "legendary": "Легендарное"}

## Raivite packs (canon §15.3): price label, amount; the first purchase of each is doubled.
const RAIVITE_SKUS := [
	["iap_raivite_s", "$0,99", 80], ["iap_raivite_m", "$4,99", 500], ["iap_raivite_l", "$9,99", 1100],
	["iap_raivite_xl", "$19,99", 2400], ["iap_raivite_xxl", "$49,99", 6500], ["iap_raivite_xxxl", "$99,99", 14000],
]
const PACK_SKUS := [
	["iap_starter", "Набор новобранца", "$1,99", "250 Райвитов, ресурсы на 8 ч, Леди Вэнс, рамка флага"],
	["iap_builder", "Пакет прораба", "$4,99", "4-й строитель навсегда + 300 Райвитов"],
	["iap_no_ads", "Без рекламы", "$4,99", "Без межстраничной рекламы навсегда, 200 Райвитов, рамка «Меценат»"],
	["iap_ration", "Паёк державы", "$4,99 / 30 дн.", "300 сразу + 60 в день при ежедневном входе"],
]

var ui: GameUI  # styles, labels, buttons, toast
var cases  # scripts/sim/cases.gd
var raivite := 0
var payments := true  # false in Russia: real-money items are hidden (canon §15.11)
var now := 0
var tab := "cases"
var _body: Control


func setup(p_ui: GameUI, p_cases, p_raivite: int, p_payments: bool, p_now: int) -> void:
	ui = p_ui
	cases = p_cases
	raivite = p_raivite
	payments = p_payments
	now = p_now
	size = Vector2(VW, VH)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_render()


func refresh(p_raivite: int, p_now: int) -> void:
	raivite = p_raivite
	now = p_now
	_render()


func _render() -> void:
	for c in get_children():
		c.queue_free()
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.45)
	dim.size = size
	add_child(dim)
	var sheet: Panel = ui._panel(self, Rect2(16, 88, VW - 32, VH - 110), ui._style(Color(0.06, 0.09, 0.15, 0.98), 22, Color(0.45, 0.6, 0.9, 0.8), 3))
	ui._at(ui._label("🏪 Лавка", 36), sheet, Vector2(30, 22))
	var bal := HBoxContainer.new()
	bal.position = Vector2(560, 26)
	var ic := TextureRect.new()
	ic.texture = load("res://assets/ui/raivite.png")
	ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ic.custom_minimum_size = Vector2(40, 40)
	bal.add_child(ic)
	bal.add_child(ui._label(str(raivite), 30))
	sheet.add_child(bal)
	ui._button(sheet, Rect2(VW - 32 - 86, 18, 64, 56), "✕", Color(0.3, 0.33, 0.42), func(): closed.emit())
	var tabs := [["cases", "Кейсы"], ["raivite", "Райвиты"], ["packs", "Наборы"], ["atelier", "Ателье"]]
	for i in tabs.size():
		var key: String = tabs[i][0]
		var on := key == tab
		ui._button(sheet, Rect2(24 + i * 218, 96, 206, 64), tabs[i][1], Color(0.16, 0.35, 0.75) if on else Color(0.14, 0.18, 0.27), func():
			tab = key
			_render())
	_body = Control.new()
	_body.position = Vector2(24, 180)
	_body.size = Vector2(VW - 80, VH - 320)
	sheet.add_child(_body)
	match tab:
		"cases":
			_cases_tab()
		"raivite":
			_raivite_tab()
		"packs":
			_packs_tab()
		"atelier":
			_atelier_tab()


func _card(rect: Rect2, color := Color(0.1, 0.15, 0.25)) -> Panel:
	return ui._panel(_body, rect, ui._style(color, 16, Color(0.45, 0.58, 0.8, 0.7), 2))


# ------------------------------------------------------------------ cases

func _cases_tab() -> void:
	# Военный ящик: free every 6 h (stores 2), +2 per day for a rewarded ad
	var free: int = cases.claim_free_crates(now)
	var c1 := _card(Rect2(0, 0, 861, 300))
	ui._at(ui._label("📦 Военный ящик", 30), c1, Vector2(24, 18))
	ui._at(ui._label("Бесплатно каждые 6 ч (копится до 2). " + cases.pity_text("case_war_crate"), 19, MUTED, false), c1, Vector2(24, 64))
	var nxt := "Готово: %d" % free if free > 0 else "Следующий через %s" % GameUI.fmt_time(cases.free_crate_left(now))
	ui._at(ui._label(nxt, 22, Color(1.0, 0.85, 0.4)), c1, Vector2(24, 100))
	ui._button(c1, Rect2(24, 150, 400, 84), "Открыть (%d)" % free, Color(0.2, 0.55, 0.3) if free > 0 else Color(0.3, 0.33, 0.42), func():
		if free > 0:
			open_case.emit("case_war_crate", 1, "free")
		else:
			ui.toast("Ящик ещё собирается"))
	ui._button(c1, Rect2(440, 150, 320, 84), "🎬 +1 за рекламу", Color(0.85, 0.55, 0.1), func(): open_case.emit("case_war_crate", 1, "ad"))
	_info_button(c1, Vector2(780, 160), "case_war_crate")
	# Королевский кейс: 160 / ×10 1440 raivites
	var c2 := _card(Rect2(0, 320, 861, 330), Color(0.16, 0.12, 0.25))
	ui._at(ui._label("👑 Королевский кейс", 30), c2, Vector2(24, 18))
	ui._at(ui._label(cases.pity_text("case_royal"), 19, Color(1.0, 0.85, 0.4), false), c2, Vector2(24, 64))
	var tgt: String = cases.target_commander
	var tname: String = String(cases.commander(tgt).get("name", tgt)) if tgt != "" else "не выбрана"
	ui._at(ui._label("«Цель»: %s (50%% эпических и легендарных осколков)" % tname, 18, MUTED, false), c2, Vector2(24, 98))
	var p1: int = cases.price("case_royal")
	ui._button(c2, Rect2(24, 150, 360, 84), "Открыть · %d 💎" % p1, Color(0.45, 0.25, 0.75), func(): open_case.emit("case_royal", 1, "raivite"))
	ui._button(c2, Rect2(400, 150, 360, 84), "×10 · %d 💎" % cases.price_x10("case_royal"), Color(0.6, 0.3, 0.85), func(): open_case.emit("case_royal", 10, "raivite"))
	ui._at(ui._label("×10 гарантирует эпическое и выше", 17, MUTED, false), c2, Vector2(400, 244))
	_info_button(c2, Vector2(780, 160), "case_royal")
	# Кейс коллекции (сезонный): no duplicates, 8 items
	var c3 := _card(Rect2(0, 670, 861, 250), Color(0.12, 0.2, 0.18))
	ui._at(ui._label("🎴 Кейс коллекции", 30), c3, Vector2(24, 18))
	ui._at(ui._label("Каждое открытие — новый предмет сезона. " + cases.pity_text("case_collection"), 19, MUTED, false), c3, Vector2(24, 64))
	var p3: int = cases.price("case_collection")
	if p3 > 0:
		ui._button(c3, Rect2(24, 130, 400, 84), "Открыть · %d 💎" % p3, Color(0.2, 0.5, 0.45), func(): open_case.emit("case_collection", 1, "raivite"))
	else:
		ui._at(ui._label("Набор сезона собран полностью!", 22, Color(0.5, 1.0, 0.6)), c3, Vector2(24, 150))
	_info_button(c3, Vector2(780, 140), "case_collection")


func _info_button(card: Control, pos: Vector2, case_id: String) -> void:
	ui._button(card, Rect2(pos, Vector2(60, 60)), "i", Color(0.25, 0.3, 0.45), func(): _show_odds(case_id))


## «i»: odds by rarity, base and effective with the current pity, before any purchase (canon §15.4).
func _show_odds(case_id: String) -> void:
	var box: Panel = ui._panel(self, Rect2(60, 420, VW - 120, 760), ui._style(Color(0.05, 0.08, 0.14, 0.99), 20, Color(0.5, 0.65, 1.0), 3))
	ui._at(ui._label("Шансы", 32), box, Vector2(30, 24))
	ui._at(ui._label("Базовые / с учётом гаранта сейчас", 19, MUTED, false), box, Vector2(30, 72))
	var y := 120.0
	for o in cases.odds(case_id):
		var r: String = o["rarity"]
		var row := ui._label("%s" % o.get("name_ru", RARITY_RU.get(r, r)), 24, RARITY_COLOR.get(r, Color.WHITE))
		ui._at(row, box, Vector2(30, y))
		var v := ui._label("%.2f%%  /  %.2f%%" % [float(o["base"]), float(o["effective"])], 24)
		v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		ui._at(v, box, Vector2(330, y), Vector2(440, 34))
		y += 54
	var pt := ui._label(cases.pity_text(case_id), 20, Color(1.0, 0.85, 0.4), false)
	pt.autowrap_mode = TextServer.AUTOWRAP_WORD
	ui._at(pt, box, Vector2(30, y + 10), Vector2(760, 60))
	ui._at(ui._label("История последних открытий хранится в профиле.", 18, MUTED, false), box, Vector2(30, y + 80))
	ui._button(box, Rect2(30, 650, VW - 180, 84), "Понятно", Color(0.13, 0.4, 0.9), func(): box.queue_free())


## Reveal after an opening: rarity glow and the list of rewards.
func show_reveal(results: Array) -> void:
	var box: Panel = ui._panel(self, Rect2(40, 300, VW - 80, 1000), ui._style(Color(0.04, 0.06, 0.11, 0.99), 24, Color(0.5, 0.65, 1.0), 3))
	var best := "common"
	var order := ["common", "rare", "epic", "legendary"]
	for r in results:
		if order.find(String(r["rarity"])) > order.find(best):
			best = r["rarity"]
	var glow: Panel = ui._panel(box, Rect2(260, 40, 341, 220), ui._style(RARITY_COLOR[best] * Color(1, 1, 1, 0.25), 110, RARITY_COLOR[best], 6))
	var title := ui._label(RARITY_RU[best] + "!", 40, RARITY_COLOR[best])
	title.size = Vector2(341, 220)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	glow.add_child(title)
	glow.scale = Vector2(0.3, 0.3)
	glow.pivot_offset = glow.size / 2
	var tw := create_tween()
	tw.tween_property(glow, "scale", Vector2.ONE, 0.45).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(30, 290)
	scroll.size = Vector2(VW - 140, 580)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var col := VBoxContainer.new()
	col.custom_minimum_size = Vector2(VW - 160, 0)
	scroll.add_child(col)
	for r in results:
		for rw in r["rewards"]:
			var l := ui._label("• " + describe(rw), 23, RARITY_COLOR.get(String(r["rarity"]), Color.WHITE), false)
			l.autowrap_mode = TextServer.AUTOWRAP_WORD
			l.custom_minimum_size = Vector2(VW - 180, 0)
			col.add_child(l)
	ui._button(box, Rect2(30, 890, VW - 140, 84), "Забрать", Color(0.2, 0.55, 0.3), func(): box.queue_free())


static func describe(rw: Dictionary) -> String:
	match String(rw.get("kind", "")):
		"res":
			var parts := PackedStringArray()
			var names := {"gold": "золота", "food": "еды", "metal": "металла"}
			var res: Dictionary = rw["res"]
			for k in res:
				if int(res[k]) > 0:
					parts.append("%d %s" % [int(res[k]), names.get(k, k)])
			return "Ресурсы: " + ", ".join(parts)
		"speedup":
			return "Ускорение %d мин" % int(rw["minutes"])
		"shards":
			return "%d осколков: %s" % [int(rw["n"]), rw.get("name", rw["commander"])]
		"cosmetic":
			return "Косметика: %s" % rw["name"]
		"glitter":
			return "Повтор → %d Блёсток" % int(rw["n"])
	return str(rw)


# ------------------------------------------------------------------ real-money tabs (stubs until store SDKs)

func _raivite_tab() -> void:
	if not payments:
		ui._at(ui._label("Покупки за деньги недоступны в вашем регионе.\nРайвиты зарабатываются в игре: задания, ящики, жилы.", 22, MUTED, false), _body, Vector2(10, 10))
		return
	for i in RAIVITE_SKUS.size():
		var sku: Array = RAIVITE_SKUS[i]
		var col := i % 2
		var row := i / 2
		var c := _card(Rect2(col * 436, row * 250, 424, 236), Color(0.08, 0.14, 0.28))
		var ic := TextureRect.new()
		ic.texture = load("res://assets/ui/raivite.png")
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.position = Vector2(24, 24)
		ic.size = Vector2(70 + row * 14, 70 + row * 14)
		c.add_child(ic)
		ui._at(ui._label(str(sku[2]), 34), c, Vector2(130, 30))
		ui._at(ui._label("Первая покупка ×2", 17, Color(1.0, 0.85, 0.4), false), c, Vector2(130, 80))
		var id: String = sku[0]
		ui._button(c, Rect2(24, 140, 376, 76), sku[1], Color(0.2, 0.55, 0.3), func(): buy_sku.emit(id))


func _packs_tab() -> void:
	if not payments:
		ui._at(ui._label("Наборы за деньги недоступны в вашем регионе.", 22, MUTED, false), _body, Vector2(10, 10))
		return
	for i in PACK_SKUS.size():
		var p: Array = PACK_SKUS[i]
		var c := _card(Rect2(0, i * 230, 861, 214), Color(0.14, 0.12, 0.22))
		ui._at(ui._label(p[1], 30), c, Vector2(24, 18))
		var d := ui._label(p[3], 20, MUTED, false)
		d.autowrap_mode = TextServer.AUTOWRAP_WORD
		ui._at(d, c, Vector2(24, 64), Vector2(540, 80))
		var id: String = p[0]
		ui._button(c, Rect2(600, 60, 236, 84), p[2], Color(0.2, 0.55, 0.3), func(): buy_sku.emit(id))


func _atelier_tab() -> void:
	var owned: Dictionary = cases.owned_cosmetics
	ui._at(ui._label("Ваша коллекция: %d предм. · Блёстки: %d" % [owned.size(), cases.glitter], 24), _body, Vector2(10, 0))
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(0, 50)
	scroll.size = Vector2(861, 1100)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_body.add_child(scroll)
	var col := VBoxContainer.new()
	col.custom_minimum_size = Vector2(850, 0)
	scroll.add_child(col)
	if owned.is_empty():
		col.add_child(ui._label("Косметика выпадает из кейсов: чернила границы, печати, салюты, узоры заливки.", 21, MUTED, false))
	for id in owned:
		var it: Dictionary = cases.cosmetic(String(id))
		if it.is_empty():
			it = {"name": str(id), "rarity": "common"}
		col.add_child(ui._label("✦ %s" % it.get("name", id), 23, RARITY_COLOR.get(String(it.get("rarity", "common")), Color.WHITE), false))
