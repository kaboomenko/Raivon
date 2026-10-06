extends SceneTree
## Headless test runner for the GDScript port of packages/sim (packages/sim/test/sim.test.ts).
## Run: godot --headless --path game --script res://tests/test_sim.gd
## TS_REF below was produced by running the TypeScript reference implementation
## (packages/sim/src) with `npx tsx`; the port must reproduce it bit for bit.

const Types := preload("res://scripts/sim/types.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")
const Rng := preload("res://scripts/sim/rng.gd")
const World := preload("res://scripts/sim/world.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const Topology := preload("res://scripts/sim/topology.gd")
const Battle := preload("res://scripts/sim/battle.gd")
const BattleAI := preload("res://scripts/sim/battle_ai.gd")
const War := preload("res://scripts/sim/war.gd")
const Armies := preload("res://scripts/sim/armies.gd")

const SEED := 20261004
const PLAYER := Types.PLAYER
const BARONS := MapGen.BARONS
const HAMLETS := MapGen.HAMLETS
const FX := Types.FX

const TS_REF := """{"rng":[{"seed":0,"u32":[3809008728,1133695204,53579671,2891528803,139681546,2203266335,104831812,1587294886],"int100":[51,85,8,53,7]},{"seed":1,"u32":[2442144158,3238099751,3819917871,2104621829,2021136066,4223536128,1515984730,2298887649],"int100":[95,18,14,92,97]},{"seed":42,"u32":[2837322924,544945897,479756282,3500138142,339756180,113173290,65323186,1112262688],"int100":[14,2,93,98,1]},{"seed":20261004,"u32":[830234368,3550070229,600957207,3558124257,130885696,2780291719,3461921206,2692557193],"int100":[27,49,7,30,13]},{"seed":4294967295,"u32":[835879718,1921286648,2356205009,1885780724,980451116,1053911718,3677392737,2464361898],"int100":[19,20,92,30,2]},{"seed":123456789,"u32":[4284103975,1001954530,2701803082,2658065534,3104308804,4033197306,2121505443,3804340767],"int100":[43,0,61,96,88]}],"maps":[{"seed":1,"fp":"ppl33ppl33wpl00ppl00mpl00ppl33pca33ppl33wpl00ppl00ppl00ppl00ppl33ppl33pfa33fpl00wpl00wpl00ppl00wpl00ppl33pmi33ppl00ppl22ppl11ppl11ppl00mpl00ppl00ppl00ppl22pci22ppl11pca11pfa11mpl00wpl00hpl00ppl22hpl22ppl22ppl11ppl11wpl00ppl00pfa22ppl22ppl22pmi22hpl00ppl00pca22ppl22ppl22ppl22wpl00pmi00pfa00fpl00fpl00hpl00|23758|-1,33,51,6"},{"seed":2,"fp":"ppl33ppl33wpl00wpl00pmi00ppl33pca33pfa33wpl00ppl00fpl00ppl33ppl33ppl33hpl00ppl00ppl00hpl00wpl00wpl00ppl33pmi33ppl22pci22ppl11ppl11hpl00ppl00fpl00fpl00hpl22pmi22ppl11pca11ppl11wpl00ppl00ppl00ppl22ppl22ppl22pfa11ppl11mpl00ppl00pfa22ppl22ppl22wpl00mpl00ppl00pca22ppl22ppl22ppl22ppl00pfa00ppl00wpl00wpl00ppl00|15840|-1,33,51,6"},{"seed":3,"fp":"ppl33ppl33pmi33ppl00wpl00ppl33pca33ppl33mpl00mpl00ppl00ppl33ppl33pfa33fpl00ppl00ppl00ppl00mpl00ppl00ppl33fpl00fpl00ppl00ppl11ppl11ppl00pfa00hpl00ppl22fpl22pmi22ppl11pca11ppl11ppl00wpl00ppl22fpl22ppl22pci22pfa11ppl11wpl00ppl00ppl22ppl22fpl22ppl22wpl00ppl00pca22pfa22ppl22wpl00pmi00ppl00ppl00mpl00wpl00mpl00|7922|-1,33,51,6"},{"seed":4,"fp":"ppl33ppl33mpl00pmi00wpl00ppl33pca33ppl33pfa33ppl00mpl00ppl00ppl33ppl33pmi33ppl00pfa00hpl00mpl00ppl33ppl00ppl00ppl22pci22ppl11ppl11ppl00wpl00ppl00fpl00ppl22pmi22ppl11pca11ppl11ppl00ppl00ppl00ppl22ppl22ppl22ppl11pfa11ppl00pfa22ppl22fpl22ppl22mpl00mpl00ppl00pca22ppl22mpl00ppl22wpl00ppl00ppl00ppl00mpl00wpl00|7923|-1,33,51,6"},{"seed":5,"fp":"ppl33ppl33fpl33ppl00wpl00ppl33pca33ppl33mpl00wpl00wpl00mpl00ppl33pfa33ppl00pfa00ppl00mpl00ppl00wpl00ppl33pmi33ppl00ppl00ppl11ppl11ppl00ppl00hpl00ppl00hpl22pci22ppl11pca11ppl11mpl00wpl00ppl00ppl22ppl22fpl22pfa11ppl11fpl00ppl00pfa22ppl22fpl22pmi22hpl22ppl00pca22ppl22ppl22wpl00ppl00ppl00pmi00mpl00fpl22ppl00|7924|-1,33,51,6"},{"seed":6,"fp":"ppl33ppl33wpl00ppl00ppl00ppl33pca33ppl33ppl00ppl00wpl00ppl33ppl33ppl33pmi33pmi00ppl00ppl00wpl00ppl00ppl00pfa33ppl00pmi22ppl11ppl11ppl00wpl00ppl00ppl00ppl22pci22pfa11pca11ppl11ppl00mpl00hpl00ppl22ppl22fpl22ppl11ppl11fpl00pfa22ppl22ppl22ppl22wpl00wpl00ppl00pca22ppl22ppl22ppl22mpl00ppl00pfa00mpl00mpl00wpl00|7925|-1,33,51,6"},{"seed":7,"fp":"ppl33ppl33ppl00ppl00ppl00ppl33pca33ppl33pmi33mpl00mpl00mpl00ppl33ppl33ppl00pfa00fpl00hpl00ppl00ppl33ppl00pfa33ppl00pci22ppl11ppl11wpl00mpl00pmi00hpl00hpl22ppl22ppl11pca11pfa11wpl00wpl00ppl00fpl22fpl22pmi22ppl11ppl11wpl00ppl00pfa22ppl22ppl22ppl22mpl00ppl00pca22ppl22wpl00ppl22mpl00ppl00ppl00fpl22ppl00ppl00|15845|-1,33,51,6"},{"seed":8,"fp":"ppl33ppl33ppl33fpl00wpl00ppl33pca33ppl33pmi33ppl00mpl00hpl33ppl33pfa33ppl00ppl00mpl00mpl00mpl00mpl00ppl00ppl00ppl22pci22ppl11ppl11wpl00mpl00ppl00ppl00fpl22pmi22ppl11pca11ppl11ppl00ppl00ppl00ppl22ppl22fpl22pfa11ppl11fpl00ppl00pfa22ppl22ppl22mpl00ppl00pfa00pca22ppl22wpl00hpl22ppl22ppl00pmi00ppl00fpl00wpl00|15846|-1,33,51,6"},{"seed":9,"fp":"ppl33ppl33hpl33wpl00ppl00ppl33pca33pfa33wpl00ppl00ppl00wpl00ppl33ppl33pmi33ppl00mpl00mpl00wpl00fpl33ppl00ppl00ppl22pci22ppl11ppl11fpl00ppl00pfa00ppl22ppl22ppl22ppl11pca11ppl11fpl00ppl00ppl00ppl22ppl22pmi22pfa11ppl11pmi00ppl00ppl22ppl22ppl22mpl00wpl00ppl00pca22pfa22ppl22wpl00wpl00ppl00ppl00mpl00ppl00ppl00|9|-1,33,51,6"},{"seed":10,"fp":"ppl33ppl33wpl00ppl00hpl00ppl33pca33ppl33wpl00ppl00mpl00ppl00ppl33ppl33pmi33ppl00ppl00ppl00mpl00ppl33fpl00pfa33pfa00ppl00pfa11ppl11ppl00ppl00ppl00ppl00fpl22pmi22ppl11pca11ppl11mpl00wpl00hpl00ppl22hpl22hpl22ppl11ppl11fpl00pfa22ppl22ppl22fpl22pci22wpl00ppl00pca22ppl22mpl00wpl00ppl22pmi00ppl00ppl22wpl00wpl00|10|-1,33,51,6"},{"seed":11,"fp":"ppl33ppl33wpl00wpl00mpl00ppl33pca33pfa33fpl00wpl00ppl00fpl33ppl33ppl33ppl00pmi00ppl00ppl00ppl00ppl33ppl00pmi33fpl00fpl22ppl11ppl11mpl00mpl00fpl00fpl00hpl22ppl22ppl11pca11ppl11wpl00pfa00ppl00ppl22ppl22pci22pfa11ppl11wpl00ppl00ppl22ppl22ppl22pmi22wpl00ppl00pca22pfa22wpl00ppl22ppl22ppl00ppl00wpl00hpl00ppl00|15849|-1,33,51,6"},{"seed":12,"fp":"ppl33ppl33pfa00ppl00fpl00ppl33pca33ppl33pmi33wpl00mpl00mpl00ppl33ppl33pfa33fpl00fpl00mpl00ppl00wpl00fpl33ppl00fpl00ppl00ppl11ppl11wpl00ppl00fpl00ppl00ppl22ppl22ppl11pca11pfa11mpl00mpl00hpl22hpl22hpl22pmi22ppl11ppl11ppl00ppl00ppl22ppl22fpl22pci22mpl00pmi00pca22ppl22ppl22mpl00ppl00ppl00pfa22wpl00ppl00ppl00|12|-1,33,51,6"},{"seed":13,"fp":"ppl33ppl33ppl33mpl00wpl00ppl33pca33ppl33wpl00wpl00wpl00wpl00ppl33ppl33pmi33ppl00ppl00pfa00ppl00wpl00pfa33ppl00ppl00pmi22pfa11ppl11mpl00ppl00ppl00hpl00ppl22ppl22ppl11pca11ppl11mpl00ppl00ppl00fpl22ppl22ppl22ppl11ppl11hpl00ppl00ppl22fpl22ppl22pci22pmi00ppl00pca22ppl22wpl00fpl22ppl00ppl00pfa22ppl00fpl00mpl00|13|-1,33,51,6"},{"seed":14,"fp":"ppl33ppl33mpl00fpl00ppl00ppl33pca33ppl33wpl00ppl00wpl00wpl00ppl33ppl33pfa33ppl00mpl00wpl00mpl00wpl00ppl33pmi33ppl00pci22ppl11ppl11hpl00fpl00ppl00hpl22ppl22ppl22pfa11pca11ppl11ppl00pmi00ppl00fpl22ppl22pmi22ppl11ppl11ppl00ppl00ppl22ppl22fpl22wpl00pfa00ppl00pca22ppl22ppl22wpl00fpl00ppl00pfa22ppl00wpl00ppl00|15852|-1,33,51,6"},{"seed":15,"fp":"ppl33ppl33wpl00mpl00wpl00ppl33pca33ppl33pfa33ppl00mpl00hpl33ppl33ppl33pmi33ppl00fpl00ppl00ppl00pfa00ppl00fpl00ppl00pmi22ppl11ppl11ppl00mpl00ppl00ppl22hpl22ppl22ppl11pca11ppl11wpl00ppl00ppl00hpl22fpl22pci22ppl11pfa11ppl00ppl00pfa22ppl22fpl22ppl22wpl00ppl00pca22ppl22wpl00ppl22mpl00pmi00ppl00ppl00wpl00mpl00|15|-1,33,51,6"},{"seed":16,"fp":"ppl33ppl33hpl33wpl00ppl00ppl33pca33ppl33pmi00fpl00ppl00ppl00ppl33pfa33pmi33ppl00hpl00mpl00wpl00ppl33ppl00fpl00pfa00ppl00ppl11pfa11wpl00wpl00ppl00ppl00ppl22pci22ppl11pca11ppl11wpl00wpl00fpl00ppl22ppl22ppl22ppl11ppl11mpl00pfa22ppl22ppl22hpl22pmi22ppl00ppl00pca22ppl22wpl00ppl22ppl00ppl00ppl00ppl22wpl00wpl00|15854|-1,33,51,6"},{"seed":17,"fp":"ppl33ppl33wpl00pmi00ppl00ppl33pca33ppl33ppl00mpl00mpl00wpl00ppl33ppl33pmi33ppl00ppl00wpl00wpl00ppl33ppl00pfa33ppl00ppl00ppl11ppl11ppl00ppl00ppl00ppl00fpl22ppl22ppl11pca11pfa11wpl00wpl00ppl00hpl22ppl22pci22ppl11ppl11ppl00ppl00ppl22ppl22ppl22pmi22wpl00ppl00pca22ppl22fpl22fpl22wpl00ppl00pfa22pfa00ppl00wpl00|17|-1,33,51,6"},{"seed":18,"fp":"ppl33ppl33wpl00mpl00mpl00ppl33pca33ppl33pmi33mpl00hpl00hpl33ppl33ppl33pfa33ppl00ppl00ppl00ppl00wpl00ppl00ppl00ppl00pmi22pfa11ppl11ppl00wpl00ppl00hpl22fpl22ppl22ppl11pca11ppl11wpl00hpl00ppl00ppl22ppl22ppl22ppl11ppl11wpl00ppl00ppl22ppl22ppl22pci22pfa00pmi00pca22pfa22wpl00ppl22mpl00ppl00ppl00ppl00wpl00ppl00|23775|-1,33,51,6"},{"seed":19,"fp":"ppl33ppl33ppl33fpl00ppl00ppl33pca33pfa33mpl00wpl00ppl00wpl00ppl33ppl33pmi33fpl00hpl00mpl00wpl00ppl00ppl33hpl00ppl22ppl00ppl11ppl11mpl00ppl00ppl00ppl00fpl22pci22ppl11pca11ppl11mpl00pfa00ppl22ppl22fpl22ppl22pfa11ppl11wpl00ppl00ppl22ppl22hpl22pmi22mpl00ppl00pca22pfa22ppl22wpl00fpl00pmi00ppl00wpl00ppl00ppl00|23776|-1,33,51,6"},{"seed":20,"fp":"ppl33ppl33ppl33wpl00ppl00ppl33pca33ppl33wpl00ppl00wpl00ppl33ppl33pfa33pmi33ppl00ppl00mpl00wpl00wpl00pfa00ppl00ppl00ppl00ppl11ppl11wpl00ppl00ppl00fpl22ppl22ppl22ppl11pca11ppl11wpl00wpl00ppl00ppl22hpl22pci22ppl11pfa11hpl00ppl00pfa22fpl22ppl22pmi22wpl00ppl00pca22ppl22ppl22ppl22ppl00ppl00pmi00wpl00ppl00ppl00|15858|-1,33,51,6"},{"seed":21,"fp":"ppl33ppl33mpl00wpl00hpl00ppl33pca33ppl33wpl00wpl00fpl00ppl33ppl33ppl33pfa33fpl00wpl00ppl00hpl00wpl00pmi00pmi33ppl00ppl00pfa11ppl11pfa00ppl00ppl00ppl00ppl22ppl22ppl11pca11ppl11wpl00mpl00fpl00ppl22ppl22pmi22ppl11ppl11fpl00ppl00pfa22hpl22ppl22fpl22pci22ppl00pca22ppl22ppl22ppl22wpl00ppl00ppl00hpl00wpl00wpl00|7940|-1,33,51,6"},{"seed":22,"fp":"ppl33ppl33ppl33wpl00mpl00ppl33pca33pfa33ppl00ppl00pmi00hpl00ppl33ppl33ppl00fpl00ppl00mpl00wpl00hpl33ppl00pmi33ppl22ppl00ppl11ppl11wpl00hpl00ppl00ppl00ppl22pmi22ppl11pca11pfa11mpl00mpl00pfa22ppl22ppl22pci22ppl11ppl11hpl00ppl00ppl22hpl22fpl22hpl22ppl00pfa00pca22ppl22wpl00ppl22wpl00ppl00ppl00mpl00wpl00ppl00|22|-1,33,51,6"},{"seed":23,"fp":"ppl33ppl33wpl00ppl00pmi00ppl33pca33ppl33pmi33fpl00wpl00ppl00ppl33ppl33pfa33fpl00wpl00wpl00mpl00wpl00fpl33ppl00ppl00hpl00ppl11ppl11mpl00ppl00ppl00ppl00ppl22pmi22ppl11pca11ppl11fpl00wpl00ppl00ppl22ppl22ppl22pfa11ppl11mpl00pfa22ppl22ppl22ppl22pci22ppl00pfa00pca22ppl22wpl00fpl22ppl00ppl00ppl22ppl00fpl00mpl00|31699|-1,33,51,6"},{"seed":24,"fp":"ppl33ppl33wpl00wpl00wpl00ppl33pca33ppl33pfa33ppl00ppl00hpl00ppl33ppl33pmi33fpl00ppl00wpl00ppl00ppl33ppl00ppl00ppl00pmi22ppl11ppl11wpl00mpl00ppl00ppl00ppl22ppl22pfa11pca11ppl11ppl00wpl00ppl00ppl22ppl22ppl22ppl11ppl11ppl00ppl00ppl22ppl22ppl22pci22ppl00pmi00pca22pfa22hpl22wpl00ppl22pfa00ppl00wpl00wpl00wpl00|7943|-1,33,51,6"},{"seed":25,"fp":"ppl33ppl33fpl00mpl00wpl00ppl33pca33ppl33pmi33wpl00wpl00wpl00ppl33ppl33ppl00hpl00pmi00wpl00wpl00fpl00fpl33pfa33ppl00ppl22ppl11ppl11wpl00mpl00pfa00hpl00fpl22pmi22pfa11pca11ppl11hpl00hpl00ppl22hpl22ppl22ppl22ppl11ppl11ppl00ppl00pfa22fpl22ppl22pci22ppl00ppl00pca22ppl22hpl22mpl00ppl00ppl00ppl00wpl00ppl00ppl00|31701|-1,33,51,6"},{"seed":26,"fp":"ppl33ppl33ppl00pfa00ppl00ppl33pca33ppl33pfa33fpl00mpl00wpl00ppl33ppl33pmi33ppl00hpl00wpl00ppl00wpl00ppl00ppl33ppl00ppl00pfa11ppl11ppl00ppl00ppl00ppl00fpl22pci22ppl11pca11ppl11mpl00ppl00ppl22ppl22hpl22fpl22ppl11ppl11ppl00ppl00ppl22ppl22ppl22pmi22wpl00pmi00pca22ppl22ppl22mpl00mpl00ppl00pfa22wpl00wpl00wpl00|15864|-1,33,51,6"},{"seed":27,"fp":"ppl33ppl33wpl00ppl00ppl00ppl33pca33ppl33wpl00hpl00mpl00ppl33ppl33ppl33pfa33ppl00fpl00wpl00ppl00wpl00ppl00pmi33pmi00hpl00ppl11ppl11mpl00wpl00ppl00ppl00ppl22pmi22pfa11pca11ppl11ppl00ppl00ppl00ppl22ppl22hpl22ppl11ppl11pfa00ppl00ppl22ppl22ppl22pci22mpl00ppl00pca22ppl22fpl22fpl22wpl00ppl00pfa22ppl00mpl00mpl00|15865|-1,33,51,6"},{"seed":28,"fp":"ppl33ppl33ppl00pmi00wpl00ppl33pca33ppl33ppl00fpl00fpl00wpl00ppl33ppl33pmi33ppl00pfa00mpl00ppl00wpl00hpl33pfa33ppl22ppl22ppl11ppl11wpl00ppl00ppl00ppl00ppl22pci22pfa11pca11ppl11mpl00mpl00ppl00ppl22fpl22ppl22ppl11ppl11ppl00pfa22ppl22ppl22ppl22pmi22wpl00ppl00pca22ppl22wpl00wpl00mpl00ppl00ppl00ppl00ppl00ppl00|28|-1,33,51,6"},{"seed":29,"fp":"ppl33ppl33ppl33ppl00mpl00ppl33pca33ppl33wpl00ppl00ppl00wpl00ppl33ppl33pmi33pmi00ppl00mpl00ppl00ppl00pfa33fpl00ppl00hpl22ppl11ppl11fpl00pfa00fpl00fpl00ppl22pmi22ppl11pca11ppl11wpl00mpl00ppl22ppl22hpl22pci22pfa11ppl11fpl00pfa22ppl22ppl22fpl22mpl00ppl00ppl00pca22ppl22mpl00wpl00wpl00ppl00ppl00ppl22ppl00wpl00|29|-1,33,51,6"},{"seed":30,"fp":"ppl33ppl33mpl00ppl00mpl00ppl33pca33ppl33pmi33ppl00wpl00ppl00ppl33ppl33hpl00ppl00wpl00hpl00wpl00wpl00ppl33pfa33ppl00ppl00ppl11ppl11wpl00ppl00ppl00pmi00ppl22ppl22ppl11pca11ppl11ppl00ppl00ppl00ppl22fpl22pmi22ppl11pfa11mpl00pfa22ppl22ppl22hpl22pci22wpl00ppl00pca22ppl22ppl22ppl22wpl00pfa00ppl00ppl00wpl00fpl00|30|-1,33,51,6"},{"seed":20261004,"fp":"ppl33ppl33wpl00mpl00ppl00ppl33pca33ppl33wpl00ppl00ppl00wpl00ppl33ppl33pmi33ppl00pmi00wpl00hpl00mpl00ppl33pfa33ppl00ppl00ppl11ppl11ppl00ppl00ppl00ppl22ppl22pmi22ppl11pca11ppl11ppl00wpl00ppl00fpl22ppl22ppl22pfa11ppl11pfa00ppl00ppl22fpl22ppl22pci22ppl00ppl00pca22ppl22wpl00ppl22wpl00ppl00pfa22mpl00mpl00ppl00|20261004|-1,33,51,6"}],"scripted":[{"seed":20261004,"out":"time;29,38,45,46;;0;3300033300003330000033001100012211100012211001122002202002000;29:43213,46:41935,40:61046,30:60974,52:66437;ev80"},{"seed":1,"out":"time;23;;1;3300033300003330000033011100002211100022211002222002222000000;23:74821,32:7500,40:63776,31:63776,30:75000;ev13"},{"seed":2,"out":"time;;;1;3300033300033300000033221100002211100022211002220002222000000;32:7500,24:75000,23:75000,40:40213,47:73462;ev15"},{"seed":3,"out":"time;29,30,31,38,39,40,46;;0;3330033300033300000030001100011111100211111002122002220000000;38:14665,29:19674,48:74126,53:7500,45:62361;ev80"},{"seed":4,"out":"time;54;;1;3300033330003330000300221100002211100022211022220002201000000;32:2851,24:7500,31:52690,23:55176,22:71609;ev74"},{"seed":5,"out":"wiped;40;;2;3330033300003300000033001100002211100022111002222202220000020;41:7500,32:7500,31:53941,39:43487,46:75000;ev24"}],"ai":[{"seed":1,"out":"time;;3300033300003330000033021100002211100022211002222002222000000;24:18750,32:18750,31:75000,40:75000,39:75000;ev1"},{"seed":2,"out":"time;;3300033300033300000033221100002211100022211002220002222000000;41:18750,24:18750,23:75000,40:75000,39:75000;ev1"},{"seed":3,"out":"time;;3330033300033300000030001100022211100222211002222002220000000;41:18750,32:18750,40:75000,31:75000,48:75000;ev1"},{"seed":4,"out":"time;;3300033330003330000300221100002211100022211022220002202000000;24:18750,32:18750,23:75000,31:75000,40:75000;ev1"},{"seed":5,"out":"time;;3330033300003300000033001100002211100022211002222202220000020;41:18750,32:18750,31:75000,40:75000,48:75000;ev1"},{"seed":6,"out":"time;;3300033300033330000003021100002211100022211022220002222000000;32:18750,24:18750,31:75000,40:75000,39:75000;ev1"},{"seed":7,"out":"time;;3300033330003300000303021100002211100022211002222002202000200;24:18750,32:18750,23:75000,31:75000,40:75000;ev1"},{"seed":8,"out":"time;;3330033330033300000000221100002211100022211002220002202200000;41:18750,24:18750,23:75000,40:75000,39:75000;ev1"},{"seed":9,"out":"time;;3330033300003330000300221100022211100022211002220002220000000;41:18750,24:18750,23:75000,40:75000,39:75000;ev1"},{"seed":10,"out":"time;;3300033300003330000303001100002211100022211022222002200200200;32:18750,41:18750,48:75000,31:75000,40:75000;ev1"}],"treaty":{"goal":48,"aiGoal":-1,"ws":{"score":60,"occupation":50,"losses":0,"battles":0,"goal":10,"capital":0,"control":80},"demands":"annex:29=3.6 annex:30=3.6 annex:31=7.1 annex:38=3.6 annex:39=3.6 annex:40=3.6 annex:46=3.6 annex:47=3.6 annex:48=14.3 annex:54=3.6 contribution:1=5 contribution:2=5 contribution:3=5 reparations=5","pkg":"annex:48 annex:31 annex:29 annex:30 annex:38 annex:39 annex:40 annex:46 annex:47 annex:54 contribution:1","annexed":"29,30,31,38,39,40,46,47,48,54","returned":""},"counter":[{"seed":1,"out":"time;;3300033300003330000033021100002211100022211002222002222000000;32:6913,41:7003,23:62716,48:61524;ev11;cmd9"},{"seed":2,"out":"time;;3300033300033300000033211100002211100022211002220002222000000;23:25000,32:6998,40:64443,22:75000;ev6;cmd10"},{"seed":3,"out":"time;;3330033300033300000030001100022211100222211002222002220000000;32:7003,41:6967,48:61261,31:61524;ev9;cmd8"},{"seed":4,"out":"time;;3300033330003330000300211100002211100022211022220002202000000;23:25000,32:6998,40:64443,22:75000;ev6;cmd12"},{"seed":5,"out":"time;;3330033300003300000033001100002111100022211002222202220000020;31:25000,41:7245,30:75000,49:64475;ev8;cmd8"},{"seed":6,"out":"time;;3300033300033330000003021100002211100022211022220002222000000;32:6967,41:7023,23:61261,40:63689;ev9;cmd11"},{"seed":7,"out":"time;;3300033330003300000303021100002211100022211002222002202000200;32:6985,41:6793,23:57911,48:65266;ev11;cmd9"},{"seed":8,"out":"time;;3330033330033300000000211100002211100022211002220002202200000;23:25000,32:7229,40:62858,22:75000;ev6;cmd10"},{"seed":9,"out":"time;;3330033300003330000300211100022211100022211002220002220000000;23:25000,32:6853,31:62512,40:74654;ev6;cmd8"},{"seed":10,"out":"time;;3300033300003330000303001100002211100022211022222002200200200;32:1824,41:7045,40:56259,48:66937;ev11;cmd15"}]}"""

var _ref: Dictionary
var _errors: Array[String] = []
var _failed := 0
var _passed := 0


func _init() -> void:
	_ref = JSON.parse_string(TS_REF)
	var tests: Array[Array] = [
		["rng matches TS xoshiro128**", _test_rng],
		["hexgrid basics", _test_hexgrid],
		["map: valid, deterministic, 50 land / 7-hex core (seeds 1..30, 20261004)", _test_map_valid],
		["map: identical to TS generator", _test_map_matches_ts],
		["topology: supply, pockets, rings", _test_topology],
		["combat: equal sides break in 6..9.5 s", _test_equal_clash],
		["combat: canon example F = 1.16 -> 1.31", _test_canon_example],
		["combat: concentration beats dispersion (Lanchester)", _test_lanchester],
		["offensive: deterministic, runs 90 s, captures hexes", _test_scripted],
		["offensive: identical to TS (seeds 20261004, 1..5)", _test_scripted_matches_ts],
		["AI never captures the player core (seeds 1..10) + identical to TS", _test_ai_core],
		["AI counteroffensive identical to TS, core safe (seeds 1..10)", _test_ai_counter],
		["cards: defense, airstrike, encircle, breakthrough", _test_cards],
		["towers hit adjacent enemy armies in clashes", _test_towers],
		["air defence: towers lvl 6+ halve airstrikes; AI airstrike targeting", _test_air_defense],
		["missile and landing cards", _test_missile_landing],
		["rivers: attacking across a river is 25% weaker", _test_river],
		["«Союзный корпус»: a temporary army for 30 s, once per offensive", _test_corps],
		["war: treaty never takes the enemy core", _test_treaty],
		["war: identical to TS (score, demands, package)", _test_treaty_matches_ts],
		["war: stars follow the canon", _test_stars],
	]
	for t in tests:
		_errors.clear()
		var started := Time.get_ticks_msec()
		(t[1] as Callable).call()
		var ms := Time.get_ticks_msec() - started
		if _errors.is_empty():
			_passed += 1
			print("PASS  %s  (%d ms)" % [t[0], ms])
		else:
			_failed += 1
			print("FAIL  %s" % t[0])
			for e in _errors.slice(0, 10):
				print("      - " + e)
	print("\n%d passed, %d failed" % [_passed, _failed])
	quit(1 if _failed > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	if not cond:
		_errors.append(msg)


func _eq(actual: Variant, expected: Variant, msg: String) -> void:
	if actual != expected:
		_errors.append("%s: expected %s, got %s" % [msg, str(expected), str(actual)])


# ---------- rng / hex ----------

func _test_rng() -> void:
	for e in _ref["rng"]:
		var r := Rng.new(int(e["seed"]))
		for i in 8:
			_eq(r.next_u32(), int(e["u32"][i]), "seed %d u32[%d]" % [int(e["seed"]), i])
		for i in 5:
			_eq(r.next_int(100), int(e["int100"][i]), "seed %d int100[%d]" % [int(e["seed"]), i])


func _test_hexgrid() -> void:
	_eq(HexGrid.disk(4).size(), 61, "disk(4) size")
	_eq(HexGrid.distance(Vector2i(0, 3), Vector2i(3, -3)), 6, "distance")
	for i in 6:
		_eq(HexGrid.dir_to(Vector2i(2, -1), HexGrid.neighbor_of(Vector2i(2, -1), i)), i, "dir_to %d" % i)
	_eq(HexGrid.DIRS[1], Vector2i(1, -1), "DIRS order")


# ---------- map ----------

func _fingerprint(w: World) -> String:
	var parts := PackedStringArray()
	for c in w.cells:
		parts.append("%s%s%d%d" % [String(c["terrain"]).substr(0, 1), String(c["kind"]).substr(0, 2), c["owner"], c["controller"]])
	var caps := PackedStringArray()
	for s in w.states:
		caps.append(str(s["capital_id"]))
	return "".join(parts) + "|" + str(w.map_seed) + "|" + ",".join(caps)


func _land_count(w: World) -> int:
	var n := 0
	for c in w.cells:
		if Types.is_passable(c):
			n += 1
	return n


func _test_map_valid() -> void:
	var a := MapGen.generate_chapter_one(SEED)
	var b := MapGen.generate_chapter_one(SEED)
	_eq(_fingerprint(a), _fingerprint(b), "deterministic")
	_eq(str(a.cells), str(b.cells), "deterministic cells")
	var seeds: Array[int] = [SEED]
	for s in range(1, 31):
		seeds.append(s)
	for s in seeds:
		var w := MapGen.generate_chapter_one(s)
		if w == null:
			_errors.append("seed %d: no map" % s)
			continue
		_eq(MapGen.validate_chapter_one(w), [] as Array[String], "seed %d problems" % s)
		_eq(_land_count(w), 50, "seed %d land" % s)
		_eq(MapGen.core_of(w, PLAYER).size(), 7, "seed %d player core" % s)


func _test_map_matches_ts() -> void:
	for e in _ref["maps"]:
		var w := MapGen.generate_chapter_one(int(e["seed"]))
		_eq(_fingerprint(w), e["fp"], "seed %d" % int(e["seed"]))


func _test_topology() -> void:
	var w := MapGen.generate_chapter_one(SEED)
	var sup := Topology.supplied(w, PLAYER)
	_eq(sup.size(), 7, "player fully supplied")
	_eq(Topology.pockets(w, BARONS, PLAYER), [], "no pockets at peace")
	# Cut a Barons front hex off: occupy every Barons hex around one non-core front hex.
	var core := MapGen.core_of(w, BARONS)
	var victim := -1
	for c in w.cells:
		if c["owner"] == BARONS and not core.has(c["id"]):
			victim = c["id"]
			break
	for n in w.neighbors[victim]:
		if n >= 0 and Types.is_passable(w.cells[n]):
			w.cells[n]["controller"] = PLAYER
	var p := Topology.pockets(w, BARONS, PLAYER)
	var found := false
	for g in p:
		if (g as Array).has(victim):
			found = true
	_check(found, "isolated hex %d should be a pocket, got %s" % [victim, str(p)])
	var rings := Topology.rings_from(w, [w.states[PLAYER]["capital_id"]], sup)
	_eq(rings.size(), 7, "rings cover the core")
	_eq(rings[w.states[PLAYER]["capital_id"]], 0, "ring 0 at seed")


# ---------- combat ----------

## A clean duel on a real map: one attacker vs one defender, no terrain or forms.
func _duel(atk: int, def: int, def_infantry: int = 0) -> Dictionary:
	var w := MapGen.generate_chapter_one(SEED)
	for c in w.cells:
		if c["controller"] != PLAYER or not Types.is_passable(c):
			continue
		for n in w.neighbors[c["id"]]:
			if n < 0 or w.cells[n]["controller"] != BARONS:
				continue
			var t: Dictionary = w.cells[n]
			for x in w.cells:
				x["fort"] = 0
			t["kind"] = "plain"
			t["terrain"] = "plain"
			t["value"] = 1
			var attacker := Armies.infantry_army(1, PLAYER, c["id"], 1, 1)
			attacker["str"] = atk * FX
			attacker["max_str"] = atk * FX
			var defender := Armies.infantry_army(101, BARONS, t["id"], 1, 1)
			defender["str"] = def * FX
			defender["max_str"] = def * FX
			defender["infantry"] = def_infantry
			var b := Battle.new(w, [attacker, defender], {"attacker": PLAYER, "defender": BARONS, "ai_energy_mult": 0, "cards": []})
			b.garrison[t["id"]] = 0
			return {"b": b, "target": t["id"], "attacker": attacker}
	assert(false, "no duel spot")
	return {}


func _test_equal_clash() -> void:
	var d := _duel(100, 91) # 100 vs 91×1.1 ≈ F 1.0
	var b: Battle = d["b"]
	var target: int = d["target"]
	var fc := b.forecast(PLAYER, [d["attacker"]["id"]], target)
	_check(fc["f"] > 0.95 and fc["f"] < 1.05, "F = %f not in (0.95, 1.05)" % fc["f"])
	_check(b.issue(PLAYER, {"t": "attack", "army": d["attacker"]["id"], "target": target}), "attack accepted")
	var ended := -1
	var i := 0
	while i < 200 and ended < 0:
		b.step()
		if b.clashes.is_empty() or b.clashes[0]["entering"] > 0:
			ended = b.tick
		i += 1
	_check(ended / 10.0 > 6.0 and ended / 10.0 < 9.5, "clash ended at %.1f s" % (ended / 10.0))


func _test_canon_example() -> void:
	# Wedge of two armies totalling 100 vs army 60 + garrison 20 behind fort 2.
	var w := MapGen.generate_chapter_one(SEED)
	var target: Dictionary = {}
	for c in w.cells:
		if c["controller"] != BARONS or c["kind"] != "plain" or c["terrain"] != "plain":
			continue
		var k := 0
		for n in w.neighbors[c["id"]]:
			if n >= 0 and w.cells[n]["controller"] == PLAYER:
				k += 1
		if k >= 2:
			target = c
			break
	if target.is_empty():
		return # map without a two-hex front: covered by other seeds
	var srcs: Array[int] = []
	for n in w.neighbors[target["id"]]:
		if n >= 0 and w.cells[n]["controller"] == PLAYER:
			srcs.append(n)
	target["fort"] = 2
	var a1 := Armies.infantry_army(1, PLAYER, srcs[0], 1, 1)
	var a2 := Armies.infantry_army(2, PLAYER, srcs[1], 1, 1)
	a1["str"] = 50 * FX; a1["max_str"] = 50 * FX
	a2["str"] = 50 * FX; a2["max_str"] = 50 * FX
	var d := Armies.infantry_army(101, BARONS, target["id"], 1, 1)
	d["str"] = 60 * FX; d["max_str"] = 60 * FX
	d["infantry"] = 0
	var b := Battle.new(w, [a1, a2, d], {"attacker": PLAYER, "defender": BARONS, "ai_energy_mult": 0, "cards": []})
	b.garrison[target["id"]] = 20 * FX
	var fc := b.forecast(PLAYER, [1, 2], target["id"])
	if fc["forms"].size() == 1:
		_check(absf(fc["f"] - 1.16) < 0.05, "F %f != 1.16" % fc["f"])
		target["fort"] = 0 # «Артобстрел»: fort −2 levels
		var f2: float = b.forecast(PLAYER, [1, 2], target["id"])["f"]
		_check(absf(f2 - 1.31) < 0.05, "F %f != 1.31" % f2)
	else:
		print("      (canon example skipped: forms %s)" % str(fc["forms"]))


func _test_lanchester() -> void:
	var d := _duel(150, 100)
	var b: Battle = d["b"]
	var strong: float = b.forecast(PLAYER, [1], d["target"])["f"]
	d["attacker"]["str"] = 75 * FX
	var weak: float = b.forecast(PLAYER, [1], d["target"])["f"]
	_check(strong / weak > 1.9, "ratio %f <= 1.9" % (strong / weak))


# ---------- full offensive ----------

func _play_scripted(seed_value: int) -> String:
	var w := MapGen.generate_chapter_one(seed_value)
	var armies := Armies.starting_armies(w)
	var war := War.declare_war(w, BARONS, War.recommend_goals(w, BARONS)[0])
	var b := Battle.new(w, armies, {"attacker": PLAYER, "defender": BARONS, "ai_energy_mult": 600, "cards": ["attack", "defense"]})
	var ai := BattleAI.new(BARONS)
	while not b.over:
		if b.tick % 20 == 0:
			# player bot: attack-all where the forecast is good, preferring the war goal
			var best_id := -1
			var best_f := 0.0
			for c in w.cells:
				if not b.can_target(PLAYER, c["id"]):
					continue
				var ids: Array = []
				for a in b.adjacent_idle_armies(PLAYER, c["id"]):
					ids.append(a["id"])
				if ids.is_empty():
					continue
				var f: float = b.forecast(PLAYER, ids, c["id"])["f"] + (0.3 if c["id"] == war["goal"] else 0.0)
				if f >= 1.2 and (best_id < 0 or f > best_f):
					best_id = c["id"]
					best_f = f
			if best_id >= 0:
				b.issue(PLAYER, {"t": "card", "card": "attack", "target": best_id})
		ai.think(b)
		b.step()
	return _battle_summary(b, w, true)


func _battle_summary(b: Battle, w: World, with_captured: bool) -> String:
	var r := b.result()
	var ctrl := PackedStringArray()
	for c in w.cells:
		ctrl.append(str(c["controller"]))
	var arm := PackedStringArray()
	for a in b.armies:
		arm.append("%d:%d" % [a["hex"], a["str"]])
	var parts := PackedStringArray([r["reason"]])
	if with_captured:
		parts.append(",".join(PackedStringArray(r["captured"])))
	parts.append(",".join(PackedStringArray(r["lost"])))
	if with_captured:
		parts.append(str(r["routed_player_armies"]))
	parts.append("".join(ctrl))
	parts.append(",".join(arm))
	parts.append("ev%d" % b.events.size())
	return ";".join(parts)


func _test_scripted() -> void:
	var a := _play_scripted(SEED)
	_eq(_play_scripted(SEED), a, "same inputs give the same result")
	var fields := a.split(";")
	_eq(fields[0], "time", "end reason")
	_check(fields[1] != "", "captured hexes: '%s'" % fields[1])


func _test_scripted_matches_ts() -> void:
	for e in _ref["scripted"]:
		_eq(_play_scripted(int(e["seed"])), e["out"], "seed %d" % int(e["seed"]))


func _test_ai_core() -> void:
	var ref := {}
	for e in _ref["ai"]:
		ref[int(e["seed"])] = e["out"]
	for s in range(1, 11):
		var w := MapGen.generate_chapter_one(s)
		var core := MapGen.core_of(w, PLAYER)
		var armies := Armies.starting_armies(w)
		# weaken the player so the AI attacks a lot
		for a in armies:
			if a["side"] == PLAYER:
				a["str"] = int(a["str"]) / 4
		var b := Battle.new(w, armies, {"attacker": PLAYER, "defender": BARONS, "ai_energy_mult": 1000, "cards": []})
		var ai := BattleAI.new(BARONS)
		while not b.over:
			ai.think(b)
			b.step()
		for id in core:
			_eq(w.cells[id]["controller"], PLAYER, "seed %d core hex %d" % [s, id])
		_eq(_battle_summary(b, w, false), ref[s], "seed %d vs TS" % s)


## Player occupies the Barons front and stands in it with weakened armies; the AI moves up,
## recaptures and plays cards. Must match the TS run exactly and never touch the player core.
func _test_ai_counter() -> void:
	var ref := {}
	for e in _ref["counter"]:
		ref[int(e["seed"])] = e["out"]
	for s in range(1, 11):
		var w := MapGen.generate_chapter_one(s)
		var bcore := MapGen.core_of(w, BARONS)
		var pcore := MapGen.core_of(w, PLAYER)
		var occ: Array = []
		for c in w.cells:
			if c["owner"] != BARONS or bcore.has(c["id"]):
				continue
			for n in w.neighbors[c["id"]]:
				if n >= 0 and w.cells[n]["owner"] == PLAYER:
					occ.append(c)
					break
		for c in occ:
			c["controller"] = PLAYER
		var armies: Array = []
		for a in Armies.starting_armies(w):
			if a["hex"] < 0 or w.cells[a["hex"]]["controller"] == a["side"]:
				armies.append(a)
		armies[0]["hex"] = occ[0]["id"]
		armies[1]["hex"] = occ[occ.size() - 1]["id"]
		for a in armies:
			if a["side"] == PLAYER:
				a["str"] = int(a["str"]) / 3
		var b := Battle.new(w, armies, {"attacker": PLAYER, "defender": BARONS, "ai_energy_mult": 1000, "cards": []})
		var ai := BattleAI.new(BARONS)
		while not b.over:
			ai.think(b)
			b.step()
		for id in pcore:
			_eq(w.cells[id]["controller"], PLAYER, "seed %d core hex %d" % [s, id])
		var ai_cmds := 0
		for l in b.command_log:
			if l["side"] == BARONS:
				ai_cmds += 1
		_eq(_battle_summary(b, w, false) + ";cmd%d" % ai_cmds, ref[s], "seed %d vs TS" % s)


func _test_cards() -> void:
	# Defense card heals and fortifies; airstrike hits armies/garrisons; encircle cuts supply.
	var d := _duel(100, 60, 1000)
	var b: Battle = d["b"]
	var target: int = d["target"]
	b.energy[BARONS] = 3000
	var def_army: Dictionary = b.army_by_id(101)
	def_army["str"] = 30 * FX
	var before: float = b.forecast(PLAYER, [1], target)["f"]
	_check(b.issue(BARONS, {"t": "card", "card": "defense", "target": target}), "defense accepted")
	b.step()
	_eq(def_army["str"], 36 * FX, "defense heals 10% of max")
	_check(b.has_effect("defense", target), "defense effect active")
	_check(b.forecast(PLAYER, [1], target)["f"] < before, "defense lowers F")
	_check(not b.card_ready(BARONS, "defense"), "defense on cooldown")
	b.energy[PLAYER] = 3000
	b.garrison[target] = 10 * FX
	_check(b.issue(PLAYER, {"t": "card", "card": "airstrike", "target": target}), "airstrike accepted")
	b.step()
	_eq(def_army["str"], 36 * FX - 12 * FX, "airstrike −20% max str")
	_check(b.has_effect("airFort", target), "airstrike lowers fort")
	b.energy[PLAYER] = 3000
	_check(b.issue(PLAYER, {"t": "card", "card": "encircle", "target": target}), "encircle accepted")
	b.step()
	_check(not b.is_supplied(target, BARONS), "encircled hex out of supply")
	_check(b.forecast(PLAYER, [1], target)["forms"].has("form.encircle"), "encircle form")
	# AI may not use attack cards on the protected player core.
	var cap: int = b.world.states[PLAYER]["capital_id"]
	_check(not b.can_target(BARONS, cap), "AI cannot target the player capital")
	# Breakthrough: a strong army takes the hex and keeps rolling in the same direction.
	var w := MapGen.generate_chapter_one(SEED)
	var armies := Armies.starting_armies(w)
	for a in armies:
		if a["side"] == PLAYER:
			a["str"] = 400 * FX
			a["max_str"] = 400 * FX
	var bb := Battle.new(w, armies, {"attacker": PLAYER, "defender": BARONS, "ai_energy_mult": 0, "cards": []})
	bb.energy[PLAYER] = 3000
	var tgt := -1
	for c in w.cells:
		if bb.can_target(PLAYER, c["id"]) and bb.adjacent_idle_armies(PLAYER, c["id"]).size() > 0:
			tgt = c["id"]
			break
	_check(bb.issue(PLAYER, {"t": "card", "card": "breakthrough", "target": tgt}), "breakthrough accepted")
	for i in 300:
		bb.step()
	_check(bb.result()["captured"].size() >= 2, "breakthrough captured %s" % str(bb.result()["captured"]))


# ---------- war ----------

func _test_treaty() -> void:
	var w := MapGen.generate_chapter_one(SEED)
	var war := War.declare_war(w, BARONS, War.recommend_goals(w, BARONS)[0])
	var w2 := MapGen.clone_world(w)
	# occupy every non-core Barons hex
	var core := MapGen.core_of(w2, BARONS)
	for c in w2.cells:
		if c["owner"] == BARONS and not core.has(c["id"]):
			c["controller"] = PLAYER
	_check(w.cells.all(func(c: Dictionary) -> bool: return c["owner"] == c["controller"]), "clone is deep")
	var ws := War.war_score(w2, war)
	_check(ws["score"] > 30, "score %s > 30" % str(ws["score"]))
	_eq(ws["control"], Types.js_round(50 + ws["score"] / 2.0), "control")
	var demands := War.available_demands(w2, war)
	for d in demands:
		for h in d["hexes"]:
			_check(not core.has(h), "demand %s takes core hex %d" % [d["id"], h])
	var pkg := War.recommend_package(w2, war, demands, ws["score"])
	var total := 0.0
	for d in pkg:
		total += d["cost"]
	_check(total <= ws["score"] + 1e-9, "package cost %f > score" % total)
	var res := War.apply_treaty(w2, war, pkg)
	for id in res["annexed"]:
		_eq(w2.cells[id]["owner"], PLAYER, "annexed %d owner" % id)
	for c in w2.cells:
		if Types.is_passable(c):
			_eq(c["controller"], c["owner"], "cell %d controller" % c["id"])
	var hamlets := 0
	for c in w2.cells:
		if c["owner"] == HAMLETS:
			hamlets += 1
	_eq(hamlets, 10, "hamlets untouched")
	for id in core:
		_eq(w2.cells[id]["owner"], BARONS, "enemy core %d stays" % id)
	# White peace returns every occupation.
	var w3 := MapGen.clone_world(w)
	for c in w3.cells:
		if c["owner"] == BARONS and not core.has(c["id"]):
			c["controller"] = PLAYER
	War.white_peace(w3)
	_eq(_fingerprint(w3), _fingerprint(w), "white peace restores the map")


func _test_treaty_matches_ts() -> void:
	var t: Dictionary = _ref["treaty"]
	var w := MapGen.generate_chapter_one(SEED)
	var war := War.declare_war(w, BARONS, War.recommend_goals(w, BARONS)[0])
	_eq(war["goal"], int(t["goal"]), "goal")
	_eq(war["ai_goal"], int(t["aiGoal"]), "ai goal")
	var w2 := MapGen.clone_world(w)
	var core := MapGen.core_of(w2, BARONS)
	for c in w2.cells:
		if c["owner"] == BARONS and not core.has(c["id"]):
			c["controller"] = PLAYER
	var ws := War.war_score(w2, war)
	for k in ["score", "occupation", "losses", "battles", "goal", "capital", "control"]:
		_check(is_equal_approx(float(ws[k]), float(t["ws"][k])), "ws.%s %s != %s" % [k, str(ws[k]), str(t["ws"][k])])
	var demands := War.available_demands(w2, war)
	var ds := PackedStringArray()
	for d in demands:
		ds.append("%s=%s" % [d["id"], _js_num(d["cost"])])
	_eq(" ".join(ds), t["demands"], "demands")
	var pkg := War.recommend_package(w2, war, demands, ws["score"])
	var ps := PackedStringArray()
	for d in pkg:
		ps.append(d["id"])
	_eq(" ".join(ps), t["pkg"], "package")
	var res := War.apply_treaty(w2, war, pkg)
	_eq(",".join(PackedStringArray(res["annexed"])), t["annexed"], "annexed")
	_eq(",".join(PackedStringArray(res["returned"])), t["returned"], "returned")


## Formats a float like JS Number#toString for the short decimals used here.
func _js_num(x: float) -> String:
	if x == floorf(x):
		return str(int(x))
	return str(x)


func _test_stars() -> void:
	_eq(War.offensive_stars([], 5, 0), 0, "no capture")
	_eq(War.offensive_stars([3], 5, 0), 1, "capture without flag")
	_eq(War.offensive_stars([5], 5, 1), 2, "flag with routed army")
	_eq(War.offensive_stars([5], 5, 0), 3, "flag, nobody routed")
	var war := {"battles": 9, "offensives": 0}
	War.record_offensive(war, 3)
	_eq(war["battles"], 10, "battle points clamp at +10")
	War.record_offensive(war, 0)
	_eq(war["battles"], 9, "no capture −1")
	_eq(war["offensives"], 2, "offensive count")


func _test_missile_landing() -> void:
	# «Ракетный удар»: army and garrison −50% current, fort −3 and the tower out to the end of the battle
	var d := _duel(100, 60)
	var b: Battle = d["b"]
	var target: int = d["target"]
	b.world.cells[target]["fort"] = 4
	b.world.cells[target]["tower"] = 3
	b.garrison[target] = 20 * FX
	var def_army: Dictionary = b.army_by_id(101)
	b.energy[PLAYER] = 5000
	_check(b.issue(PLAYER, {"t": "card", "card": "missile", "target": target}), "missile accepted")
	b.step()
	_eq(def_army["str"], 30 * FX, "missile halves the army")
	_eq(b.garrison[target], 10 * FX, "missile halves the garrison")
	_eq(b.effective_fort(target), 1, "fort 4 − 3 to the end of the battle")
	for i in 400:
		b.step()
	_eq(b.effective_fort(target), 1, "still −3 after 40 s")
	# «Десант»: an empty hex without a fort within 2 of our land; a 40% copy lands and attacks in 1.5 s
	var d2 := _duel(100, 60)
	var b2: Battle = d2["b"]
	var near := -1
	for c in b2.world.cells:
		if c["controller"] == BARONS and b2.army_at(c["id"], BARONS) == null and int(c["fort"]) == 0 and b2.can_land(PLAYER, c["id"]):
			near = c["id"]
			break
	_check(near >= 0, "a landing hex exists")
	b2.world.cells[d2["target"]]["fort"] = 2
	_check(not b2.can_land(PLAYER, d2["target"]), "no landing on a hex with an army or a fort")
	b2.energy[PLAYER] = 5000
	b2.garrison[near] = 5 * FX
	_check(b2.issue(PLAYER, {"t": "card", "card": "landing", "target": near}), "landing accepted")
	b2.step()
	var copy: Variant = null
	for a in b2.armies:
		if a.has("landing"):
			copy = a
	_check(copy != null and int(copy["max_str"]) == 40 * FX, "a 40%% copy lands")
	for i in 120:
		b2.step()
	_check(int(b2.world.cells[near]["controller"]) == PLAYER and b2.landing_held(PLAYER), "the landing takes and holds the hex")


func _test_air_defense() -> void:
	# Barons' army at the target with a tower next door: lvl 5 — full damage, lvl 6 — half and a flak event.
	for lvl in [5, 6]:
		var d := _duel(100, 60)
		var b: Battle = d["b"]
		var target: int = d["target"]
		var tower_hex := -1
		for n in b.world.neighbors[target]:
			if n >= 0 and b.world.cells[n]["controller"] == BARONS and b.world.cells[n]["owner"] == BARONS:
				tower_hex = n
				break
		_check(tower_hex >= 0, "a Barons hex next to the target")
		b.world.cells[tower_hex]["tower"] = lvl
		var def_army: Dictionary = b.army_by_id(101)
		b.energy[PLAYER] = 3000
		_check(b.air_defended(target, BARONS) == (lvl >= 6), "tower lvl %d air defence" % lvl)
		_check(not b.air_defended(target, PLAYER), "the enemy tower doesn't defend the player")
		_check(b.issue(PLAYER, {"t": "card", "card": "airstrike", "target": target}), "airstrike accepted")
		b.step()
		var lost: int = 60 * FX - int(def_army["str"])
		_eq(lost, (12 if lvl < 6 else 6) * FX, "airstrike damage under tower lvl %d" % lvl)
		var flak := b.events.filter(func(e: Dictionary) -> bool: return e["type"] == "flak")
		_check(flak.is_empty() == (lvl < 6), "flak event only under air defence (lvl %d)" % lvl)
	# AI picks a centre with enough enemy Strength; nothing when the player is spread thin.
	var d2 := _duel(100, 60)
	var b2: Battle = d2["b"]
	b2.energy[BARONS] = 3000
	var t := BattleAI.airstrike_target(b2, BARONS)
	_check(t >= 0, "AI finds an airstrike centre near a big army (100 vs avg 60)")
	_check(b2.airstrike_area(t).has(int(d2["attacker"]["hex"])), "the centre covers the player's army")
	d2["attacker"]["max_str"] = 80 * FX
	_eq(BattleAI.airstrike_target(b2, BARONS), -1, "no airstrike below 1.5 × own average (80 < 90)")
	var ai := BattleAI.new(BARONS)
	ai.airstrike = true
	d2["attacker"]["max_str"] = 100 * FX
	b2.tick = 4
	b2.step()
	ai.think(b2)
	b2.step()
	_check(not b2.card_ready(BARONS, "airstrike"), "AI with the card plays the airstrike")


func _test_towers() -> void:
	var lost := []
	for lvl in [0, 1, 4]:
		var d := _duel(100, 91)
		var b: Battle = d["b"]
		var src: int = d["attacker"]["hex"]
		b.world.cells[src]["tower"] = lvl
		var def: Dictionary = b.army_by_id(101)
		var before: int = def["str"]
		b.step()  # idle: no clash, no tower damage
		_check(int(def["str"]) == before, "tower lvl %d silent outside a clash" % lvl)
		b.issue(PLAYER, {"t": "attack", "army": d["attacker"]["id"], "target": d["target"]})
		for i in 20:
			b.step()
		lost.append(before - int(def["str"]))
	# 20 ticks = 2 s: tower lvl 1 adds 2 × 1.5 = 3 Strength; lvl 4 × М_силы 1.9 = 5.7 (minus a tick of joining)
	var extra1: int = int(lost[1]) - int(lost[0])
	var extra4: int = int(lost[2]) - int(lost[0])
	_check(extra1 >= 2 * FX and extra1 <= 32 * FX / 10, "tower lvl 1 adds ~1.5 Strength/s (%.2f in 2 s)" % (extra1 / float(FX)))
	_check(extra4 > extra1 * 18 / 10, "tower lvl 4 hits ×1.9 harder (%.2f)" % (extra4 / float(FX)))
	# occupied hex: tower works for nobody
	var d2 := _duel(100, 91)
	var b2: Battle = d2["b"]
	var src2: int = d2["attacker"]["hex"]
	b2.world.cells[src2]["tower"] = 5
	b2.world.cells[src2]["controller"] = BARONS
	var def2: Dictionary = b2.army_by_id(101)
	def2["hex"] = d2["target"]
	b2.world.cells[src2]["controller"] = PLAYER
	b2.world.cells[src2]["owner"] = BARONS  # player occupies a Barons hex with a Barons tower
	var str0: int = def2["str"]
	b2.issue(PLAYER, {"t": "attack", "army": d2["attacker"]["id"], "target": d2["target"]})
	for i in 20:
		b2.step()
	var d3 := _duel(100, 91)
	var b3: Battle = d3["b"]
	var def3: Dictionary = b3.army_by_id(101)
	b3.issue(PLAYER, {"t": "attack", "army": d3["attacker"]["id"], "target": d3["target"]})
	for i in 20:
		b3.step()
	_check(str0 - int(def2["str"]) == int(def3["max_str"]) - int(def3["str"]), "tower on an occupied hex is silent")


func _test_river() -> void:
	var d := _duel(100, 91)
	var b: Battle = d["b"]
	var src: int = d["attacker"]["hex"]
	var f0: float = b.forecast(PLAYER, [d["attacker"]["id"]], d["target"])["f"]
	b.world.rivers[World.edge_key(src, d["target"])] = true
	var f1: float = b.forecast(PLAYER, [d["attacker"]["id"]], d["target"])["f"]
	b.world.rivers = {}
	_check(f1 < f0 and absf(f1 * f1 / (f0 * f0) - 0.75) < 0.02, "F across a river %.3f vs %.3f (W ×0.75)" % [f1, f0])


func _test_corps() -> void:
	var d := _duel(100, 91)
	var b: Battle = d["b"]
	var t: int = d["target"]
	var spot := -1
	for n in b.world.neighbors[t]:
		if n >= 0 and b.world.cells[n]["controller"] == PLAYER and b.army_at(n, PLAYER) == null and Types.is_passable(b.world.cells[n]):
			spot = n
			break
	if spot < 0:
		print("      (no free front hex for the corps on this map)")
		return
	_check(not b.validate(PLAYER, {"t": "card", "card": "corps", "target": spot}), "no corps without an ally in the war")
	b.opts["cards"] = ["attack", "corps"]
	b.energy[PLAYER] = 10 * Battle.ENERGY_UNIT
	var n0 := b.armies.size()
	_check(b.issue(PLAYER, {"t": "card", "card": "corps", "target": spot}), "corps card accepted on a free front hex")
	b.step()
	_check(b.armies.size() == n0 + 1 and b.army_at(spot, PLAYER) != null, "temporary army appears")
	var corps: Dictionary = b.army_at(spot, PLAYER)
	_check(int(corps["max_str"]) == 30 * FX, "strength = 30%% of the average (%d)" % int(corps["max_str"]))
	b.energy[PLAYER] = 10 * Battle.ENERGY_UNIT
	var other := -1
	for n in b.world.neighbors[t]:
		if n >= 0 and n != spot and b.world.cells[n]["controller"] == PLAYER and b.army_at(n, PLAYER) == null:
			other = n
	_check(other < 0 or not b.validate(PLAYER, {"t": "card", "card": "corps", "target": other}), "only once per offensive")
	for i in Battle.CORPS_TICKS:
		b.step()
	_check(b.armies.size() == n0, "the corps leaves after 30 s")
