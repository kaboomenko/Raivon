// Storage behind the API: an in-memory store for tests/dev and PostgreSQL for production.
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import pg from "pg";

export interface Player { id: string; deviceId: string; country: string | null }
export interface SaveRow { rev: number; savedAt: Date; data: unknown }
export type PutResult = { ok: true; rev: number; savedAt: Date } | { ok: false; currentRev: number };

export interface Store {
  findOrCreatePlayer(deviceId: string, country: string | null): Promise<{ player: Player; created: boolean }>;
  getPlayer(id: string): Promise<Player | null>;
  getSave(playerId: string): Promise<SaveRow | null>;
  /** Optimistic concurrency: succeeds only when baseRev equals the stored revision (0 = no save yet). */
  putSave(playerId: string, baseRev: number, data: unknown, now: Date): Promise<PutResult>;
  close(): Promise<void>;
}

export class MemoryStore implements Store {
  private players = new Map<string, Player>();
  private byDevice = new Map<string, string>();
  private saves = new Map<string, SaveRow>();

  async findOrCreatePlayer(deviceId: string, country: string | null) {
    const id = this.byDevice.get(deviceId);
    if (id) return { player: this.players.get(id)!, created: false };
    const player: Player = { id: randomUUID(), deviceId, country };
    this.players.set(player.id, player);
    this.byDevice.set(deviceId, player.id);
    return { player, created: true };
  }

  async getPlayer(id: string) {
    return this.players.get(id) ?? null;
  }

  async getSave(playerId: string) {
    return this.saves.get(playerId) ?? null;
  }

  async putSave(playerId: string, baseRev: number, data: unknown, now: Date): Promise<PutResult> {
    const cur = this.saves.get(playerId);
    const currentRev = cur?.rev ?? 0;
    if (baseRev !== currentRev) return { ok: false, currentRev };
    const row = { rev: currentRev + 1, savedAt: now, data };
    this.saves.set(playerId, row);
    return { ok: true, rev: row.rev, savedAt: now };
  }

  async close() {}
}

export class PgStore implements Store {
  constructor(private pool: pg.Pool) {}

  static async connect(url: string): Promise<PgStore> {
    const pool = new pg.Pool({ connectionString: url, max: 10 });
    const sql = readFileSync(new URL("../sql/001_init.sql", import.meta.url), "utf8");
    await pool.query(sql);
    return new PgStore(pool);
  }

  async findOrCreatePlayer(deviceId: string, country: string | null) {
    const id = randomUUID();
    const r = await this.pool.query(
      `INSERT INTO players (id, device_id, country) VALUES ($1, $2, $3)
       ON CONFLICT (device_id) DO UPDATE SET last_seen = now()
       RETURNING id, device_id, country, (xmax = 0) AS created`,
      [id, deviceId, country],
    );
    const row = r.rows[0];
    return { player: { id: row.id, deviceId: row.device_id, country: row.country }, created: row.created };
  }

  async getPlayer(id: string) {
    const r = await this.pool.query("SELECT id, device_id, country FROM players WHERE id = $1", [id]);
    const row = r.rows[0];
    return row ? { id: row.id, deviceId: row.device_id, country: row.country } : null;
  }

  async getSave(playerId: string) {
    const r = await this.pool.query("SELECT rev, saved_at, data FROM saves WHERE player_id = $1", [playerId]);
    const row = r.rows[0];
    return row ? { rev: row.rev, savedAt: row.saved_at, data: row.data } : null;
  }

  async putSave(playerId: string, baseRev: number, data: unknown, now: Date): Promise<PutResult> {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const cur = await client.query("SELECT rev FROM saves WHERE player_id = $1 FOR UPDATE", [playerId]);
      const currentRev: number = cur.rows[0]?.rev ?? 0;
      if (baseRev !== currentRev) {
        await client.query("ROLLBACK");
        return { ok: false, currentRev };
      }
      await client.query(
        `INSERT INTO saves (player_id, rev, saved_at, data) VALUES ($1, $2, $3, $4)
         ON CONFLICT (player_id) DO UPDATE SET rev = EXCLUDED.rev, saved_at = EXCLUDED.saved_at, data = EXCLUDED.data`,
        [playerId, currentRev + 1, now, JSON.stringify(data)],
      );
      await client.query("COMMIT");
      return { ok: true, rev: currentRev + 1, savedAt: now };
    } catch (e) {
      await client.query("ROLLBACK");
      throw e;
    } finally {
      client.release();
    }
  }

  async close() {
    await this.pool.end();
  }
}
