// Store contract: the same behaviour for MemoryStore and PgStore (PG runs when TEST_DATABASE_URL is set).
import { afterAll, describe, expect, it } from "vitest";
import { MemoryStore, PgStore, type Store } from "../src/store.js";

const factories: [string, () => Promise<Store>][] = [["memory", async () => new MemoryStore()]];
if (process.env.TEST_DATABASE_URL) {
  factories.push(["postgres", async () => {
    const s = await PgStore.connect(process.env.TEST_DATABASE_URL!);
    // isolate runs: each test uses fresh device ids, so no truncation is needed
    return s;
  }]);
}

const opened: Store[] = [];
afterAll(async () => {
  for (const s of opened) await s.close();
});

for (const [name, make] of factories) {
  describe(`store: ${name}`, () => {
    it("creates a player once per device", async () => {
      const s = await make();
      opened.push(s);
      const dev = `dev-${name}-${Math.random()}`;
      const a = await s.findOrCreatePlayer(dev, "UA");
      const b = await s.findOrCreatePlayer(dev, "UA");
      expect(a.created).toBe(true);
      expect(b.created).toBe(false);
      expect(b.player.id).toBe(a.player.id);
      expect((await s.getPlayer(a.player.id))?.country).toBe("UA");
    });

    it("saves with optimistic revisions", async () => {
      const s = await make();
      opened.push(s);
      const { player } = await s.findOrCreatePlayer(`dev-${name}-${Math.random()}`, null);
      expect(await s.getSave(player.id)).toBeNull();
      const t = new Date("2026-10-05T10:00:00Z");
      const r1 = await s.putSave(player.id, 0, { version: 1, n: 1 }, t);
      expect(r1).toMatchObject({ ok: true, rev: 1 });
      expect(await s.putSave(player.id, 0, { version: 1, n: 2 }, t)).toEqual({ ok: false, currentRev: 1 });
      const r2 = await s.putSave(player.id, 1, { version: 1, n: 3 }, t);
      expect(r2).toMatchObject({ ok: true, rev: 2 });
      const got = await s.getSave(player.id);
      expect(got?.rev).toBe(2);
      expect((got?.data as { n: number }).n).toBe(3);
    });
  });
}
