// HTTP API v1 (docs/gdd/12 §6.6, subset): bootstrap, guest auth, cloud save.
import Fastify, { type FastifyInstance, type FastifyRequest } from "fastify";
import { SignJWT, jwtVerify } from "jose";
import type { Store } from "./store.js";

export interface AppOptions {
  store: Store;
  jwtSecret: string;
  /** Feature flags sent to clients; alliances stay off until the owner's signal (decision 24). */
  flags?: Record<string, boolean>;
  now?: () => Date;
  minClientVersion?: string;
}

const MAX_SAVE_BYTES = 512 * 1024;
/** Countries where real-money purchases are hidden (decision 16: Russia — ads only). */
const NO_PAYMENT_COUNTRIES = new Set(["RU"]);

export function buildApp(opts: AppOptions): FastifyInstance {
  const app = Fastify({ logger: false, bodyLimit: MAX_SAVE_BYTES + 4096 });
  const key = new TextEncoder().encode(opts.jwtSecret);
  const now = opts.now ?? (() => new Date());
  const flags = { alliances: false, ...opts.flags };

  async function auth(req: FastifyRequest): Promise<string | null> {
    const h = req.headers.authorization;
    if (!h?.startsWith("Bearer ")) return null;
    try {
      const { payload } = await jwtVerify(h.slice(7), key, { issuer: "raivon" });
      return typeof payload.sub === "string" ? payload.sub : null;
    } catch {
      return null;
    }
  }

  // Store country: header from the store SDK / Cloudflare (CF-IPCountry) — used for the payments switch.
  function country(req: FastifyRequest): string | null {
    const c = (req.headers["x-store-country"] ?? req.headers["cf-ipcountry"]) as string | undefined;
    return c ? c.toUpperCase().slice(0, 2) : null;
  }

  app.get("/healthz", async () => ({ ok: true }));

  app.get("/v1/bootstrap", async (req) => {
    const c = country(req);
    return {
      server_time: Math.floor(now().getTime() / 1000),
      min_client_version: opts.minClientVersion ?? "0.6.0",
      flags,
      payments: !(c && NO_PAYMENT_COUNTRIES.has(c)),
      country: c,
    };
  });

  app.post<{ Body: { device_id?: string } }>("/v1/auth/guest", async (req, reply) => {
    const deviceId = req.body?.device_id;
    if (typeof deviceId !== "string" || deviceId.length < 8 || deviceId.length > 128) {
      return reply.code(400).send({ error: "E_DEVICE_ID" });
    }
    const { player, created } = await opts.store.findOrCreatePlayer(deviceId, country(req));
    const token = await new SignJWT({}).setProtectedHeader({ alg: "HS256" }).setSubject(player.id)
      .setIssuer("raivon").setIssuedAt().setExpirationTime("30d").sign(key);
    return { player_id: player.id, token, created };
  });

  app.get("/v1/save", async (req, reply) => {
    const pid = await auth(req);
    if (!pid) return reply.code(401).send({ error: "E_AUTH" });
    const s = await opts.store.getSave(pid);
    if (!s) return { rev: 0, saved_at: null, data: null };
    return { rev: s.rev, saved_at: Math.floor(new Date(s.savedAt).getTime() / 1000), data: s.data };
  });

  app.put<{ Body: { base_rev?: number; data?: unknown } }>("/v1/save", async (req, reply) => {
    const pid = await auth(req);
    if (!pid) return reply.code(401).send({ error: "E_AUTH" });
    const { base_rev, data } = req.body ?? {};
    if (typeof base_rev !== "number" || !Number.isInteger(base_rev) || base_rev < 0) {
      return reply.code(400).send({ error: "E_BASE_REV" });
    }
    const problem = validateSave(data);
    if (problem) return reply.code(422).send({ error: problem });
    const r = await opts.store.putSave(pid, base_rev, data, now());
    if (!r.ok) return reply.code(409).send({ error: "E_CONFLICT", current_rev: r.currentRev });
    return { rev: r.rev, saved_at: Math.floor(r.savedAt.getTime() / 1000) };
  });

  return app;
}

/** Shape checks for the client save (scripts/save.gd): cheap sanity, not full authority yet. */
export function validateSave(data: unknown): string | null {
  if (!data || typeof data !== "object" || Array.isArray(data)) return "E_SAVE_SHAPE";
  const d = data as Record<string, unknown>;
  if (d.version !== 1) return "E_SAVE_VERSION";
  if (typeof d.seed !== "number") return "E_SAVE_SEED";
  if (!Array.isArray(d.cells) || d.cells.length > 2000) return "E_SAVE_CELLS";
  if (JSON.stringify(data).length > MAX_SAVE_BYTES) return "E_SAVE_SIZE";
  const econ = d.econ as Record<string, unknown> | undefined;
  if (econ) {
    const res = econ.res as Record<string, unknown> | undefined;
    for (const [k, v] of Object.entries(res ?? {})) {
      if (typeof v !== "number" || v < 0 || !Number.isFinite(v)) return `E_SAVE_RES_${k.toUpperCase()}`;
    }
  }
  return null;
}
