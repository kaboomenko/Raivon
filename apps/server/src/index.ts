// Entry point: RAIVON_ROLE=api (default). DATABASE_URL → PostgreSQL, otherwise an in-memory store (dev only).
import { buildApp } from "./app.js";
import { MemoryStore, PgStore, type Store } from "./store.js";

const port = Number(process.env.PORT ?? 8080);
const secret = process.env.JWT_SECRET ?? "";
if (process.env.NODE_ENV === "production" && secret.length < 32) {
  throw new Error("JWT_SECRET must be set (≥32 chars) in production");
}
const store: Store = process.env.DATABASE_URL ? await PgStore.connect(process.env.DATABASE_URL) : new MemoryStore();
const app = buildApp({ store, jwtSecret: secret || "dev-secret-dev-secret-dev-secret!!" });
await app.listen({ port, host: "0.0.0.0" });
console.log(`raivon api on :${port} (${process.env.DATABASE_URL ? "postgres" : "memory"})`);
