# Сервер Raivon (v0.1)

Код: `apps/server` (Fastify + PostgreSQL 16, TypeScript, запуск через `tsx`). Спецификация — `docs/gdd/12_tech_analytics_roadmap.md` §6–8; сейчас реализован первый срез.

## Что умеет
| Метод | Путь | Назначение |
|---|---|---|
| GET | `/healthz` | живость |
| GET | `/v1/bootstrap` | время сервера, минимальная версия клиента, флаги (`alliances: false` — решение 24), `payments` по стране стора (RU → только реклама, решение 16) |
| POST | `/v1/auth/guest` `{device_id}` | гостевой аккаунт по id устройства → JWT на 30 дней |
| GET | `/v1/save` | облачное сохранение `{rev, saved_at, data}` |
| PUT | `/v1/save` `{base_rev, data}` | запись с оптимистичной блокировкой: 409 при чужой ревизии; проверка формы сохранения (версия, сид, клетки, ресурсы ≥ 0, ≤ 512 КБ) |

## Запуск
- Разработка: `npm run dev -w @raivon/server` (без `DATABASE_URL` — хранилище в памяти).
- Тесты: `npx vitest run --root apps/server`; с настоящим PostgreSQL: `TEST_DATABASE_URL=postgres://… npx vitest run --root apps/server`.
- Прод (один VPS, ~5–10 €/мес): `cd apps/server && cp .env.example .env` (задать `JWT_SECRET` ≥ 32 символов и `PGPASSWORD`) → `docker compose up -d`. Перед API — Cloudflare (бесплатный план): TLS, WAF, заголовок `CF-IPCountry`.

## Дальше (по `12` §6–7)
Авторитетная экономика и ленивая симуляция мира на сервере (порт `scripts/sim/*` в TypeScript, проверка паритетом как для боя), перепроверка боёв по логу, валидация покупок (RevenueCat), SSV рекламы, пуши FCM (уведомления о набегах — решение 21), удаление аккаунта, бэкапы WAL-G.
