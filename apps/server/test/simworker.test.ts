// Runs only where a Godot binary exists (CI downloads one; local dev: /opt/godot or GODOT_BIN).
import { existsSync, readFileSync } from "node:fs";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { SimPool } from "../src/simworker.js";

it("a missing Godot binary fails calls cleanly instead of crashing", async () => {
  const p = new SimPool("/nonexistent/godot", 1);
  await expect(p.call("ping", {}, 2000)).rejects.toThrow();
  p.close();
});

const bin = process.env.GODOT_BIN ?? "/opt/godot/Godot_v4.5.1-stable_linux.x86_64";
const run = existsSync(bin) ? describe : describe.skip;

run("sim worker (headless Godot)", () => {
  let pool: SimPool;
  beforeAll(() => {
    pool = new SimPool(bin, 1);
  });
  afterAll(() => pool?.close());

  it("answers ping", async () => {
    expect(await pool.call("ping", {}, 60000)).toMatchObject({ ok: true, pong: true });
  }, 70000);

  it("computes the economy of a client save with the client's own rules", async () => {
    const save = JSON.parse(readFileSync(new URL("./fixture_save.json", import.meta.url), "utf8"));
    const r = await pool.call("income", { save, now: save.saved_at + 3600 }, 60000);
    expect(r.ok).toBe(true);
    expect(r.dl).toBe(1);
    const inc = r.income_per_hour as Record<string, number>;
    expect(inc.gold).toBeGreaterThan(0);
    const stock = r.stock as Record<string, number>;
    expect(stock.gold).toBeGreaterThanOrEqual(inc.gold - 1); // one hour of income accrued on the hexes
  }, 70000);

  it("rejects unknown commands", async () => {
    expect(await pool.call("nope", {}, 60000)).toMatchObject({ ok: false, error: "E_CMD" });
  }, 70000);
});
