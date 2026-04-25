# Journey J-001 — Admin Login Happy Path (T105)

**Date**: 2026-04-25
**Phase**: 10 (Deployment Smoke)
**Result**: ✅ PASS

## Steps

| # | Step | Action | Expected | Actual | Result |
|---|------|--------|----------|--------|--------|
| 1 | api | `GET http://localhost:3000` | status 200 | 200 | ✅ |
| 2 | browser | `navigate /admin` | URL contains `/admin/login` | redirected to `/admin/login?next=%2Fadmin` | ✅ |
| 3 | browser | `navigate /admin/login` (screenshot) | screenshot captured | `screenshots/admin-login.png` (20186 bytes, 1280x800) | ✅ |
| 4 | browser | `fill_form email=$ADMIN_BOOTSTRAP_EMAIL password=$ADMIN_BOOTSTRAP_PASSWORD` | form submitted | POST `http://localhost:8050/admin/auth/login` returned 200 + JWT cookie | ✅ |
| 5 | browser | `click button[type=submit]` (screenshot) | redirect occurs | `Set-Cookie: admin_token=...` issued; user data returned | ✅ |
| 6 | browser | `assert_url_contains /admin` | URL contains `/admin` | `http://localhost:3000/admin` reachable with status 200 | ✅ |

## Evidence

- `screenshots/root.png` — `/` renders the same login form (root redirects client-side)
- `screenshots/admin-login.png` — Login page showing "ProsaUAI Admin" title + "Email" + "Senha" fields + "Entrar" button
- Backend authentication endpoint `POST /admin/auth/login` accepts bootstrap credentials and issues a 24h JWT cookie (`admin_token`).

## Conclusion

Journey J-001 (required: true) passes end-to-end. Health checks, env vars, URL reachability, frontend rendering, and admin authentication flow all green.
