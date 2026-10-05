import { describe, expect, it } from "vitest";
import { buildApp, validateSave } from "../src/app.js";
import { MemoryStore } from "../src/store.js";

const SECRET = "test-secret-test-secret-test-secret";
const save = (gold = 100) => ({ version: 1, seed: 20261004, cells: [[1, 1, 0]], econ: { res: { gold, food: 1, metal: 1, raivite: 50 } } });

async function setup(now = new Date("2026-10-05T12:00:00Z")) {
  const app = buildApp({ store: new MemoryStore(), jwtSecret: SECRET, now: () => now });
  const r = await app.inject({ method: "POST", url: "/v1/auth/guest", payload: { device_id: "device-123456" } });
  return { app, token: r.json().token as string, player: r.json().player_id as string };
}

describe("bootstrap", () => {
  it("returns server time, flags with alliances off and payments by country", async () => {
    const { app } = await setup();
    const a = await app.inject({ method: "GET", url: "/v1/bootstrap" });
    expect(a.json().server_time).toBe(Math.floor(Date.parse("2026-10-05T12:00:00Z") / 1000));
    expect(a.json().flags.alliances).toBe(false);
    expect(a.json().payments).toBe(true);
    const ru = await app.inject({ method: "GET", url: "/v1/bootstrap", headers: { "x-store-country": "ru" } });
    expect(ru.json().payments).toBe(false);
  });
});

describe("guest auth", () => {
  it("is idempotent per device and rejects bad ids", async () => {
    const { app, player } = await setup();
    const again = await app.inject({ method: "POST", url: "/v1/auth/guest", payload: { device_id: "device-123456" } });
    expect(again.json().player_id).toBe(player);
    expect(again.json().created).toBe(false);
    const bad = await app.inject({ method: "POST", url: "/v1/auth/guest", payload: { device_id: "x" } });
    expect(bad.statusCode).toBe(400);
  });
});

describe("cloud save", () => {
  it("requires auth", async () => {
    const { app } = await setup();
    expect((await app.inject({ method: "GET", url: "/v1/save" })).statusCode).toBe(401);
    expect((await app.inject({ method: "GET", url: "/v1/save", headers: { authorization: "Bearer junk" } })).statusCode).toBe(401);
  });

  it("stores revisions with optimistic concurrency", async () => {
    const { app, token } = await setup();
    const h = { authorization: `Bearer ${token}` };
    expect((await app.inject({ method: "GET", url: "/v1/save", headers: h })).json().rev).toBe(0);
    const p1 = await app.inject({ method: "PUT", url: "/v1/save", headers: h, payload: { base_rev: 0, data: save(100) } });
    expect(p1.json().rev).toBe(1);
    const stale = await app.inject({ method: "PUT", url: "/v1/save", headers: h, payload: { base_rev: 0, data: save(200) } });
    expect(stale.statusCode).toBe(409);
    expect(stale.json().current_rev).toBe(1);
    const p2 = await app.inject({ method: "PUT", url: "/v1/save", headers: h, payload: { base_rev: 1, data: save(300) } });
    expect(p2.json().rev).toBe(2);
    const g = await app.inject({ method: "GET", url: "/v1/save", headers: h });
    expect(g.json().data.econ.res.gold).toBe(300);
  });

  it("rejects malformed saves", async () => {
    const { app, token } = await setup();
    const h = { authorization: `Bearer ${token}` };
    const bad = await app.inject({ method: "PUT", url: "/v1/save", headers: h, payload: { base_rev: 0, data: { version: 2 } } });
    expect(bad.statusCode).toBe(422);
    expect(validateSave(save(-5))).toBe("E_SAVE_RES_GOLD");
    expect(validateSave(save(5))).toBeNull();
  });

  it("isolates players", async () => {
    const { app, token } = await setup();
    await app.inject({ method: "PUT", url: "/v1/save", headers: { authorization: `Bearer ${token}` }, payload: { base_rev: 0, data: save(1) } });
    const other = await app.inject({ method: "POST", url: "/v1/auth/guest", payload: { device_id: "device-other-1" } });
    const g = await app.inject({ method: "GET", url: "/v1/save", headers: { authorization: `Bearer ${other.json().token}` } });
    expect(g.json().rev).toBe(0);
  });
});
