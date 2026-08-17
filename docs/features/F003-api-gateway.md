# F003 — API Gateway (HTTP API)

| Feld | Wert |
|------|------|
| **ID** | F003 |
| **Name** | API Gateway (HTTP API) |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 2 |
| **Abhängigkeiten** | F001 |
| **Fachquelle** | `architecture/architecture-decisions.md` (ADR-004), `api/endpoints.md` |

## Beschreibung

HTTP API (API Gateway V2) mit Cognito-JWT-Autorisator und Lambda-Integration für die
Endpunkte `POST /orders`, `GET /orders/{orderId}`, `GET /orders`, `PATCH /orders/{orderId}/status`.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T003-01 | HTTP API + Integration + Route `POST /orders` | ⏳ PLANNED |
| T003-02 | Route `GET /orders/{orderId}` | ⏳ PLANNED |
| T003-03 | Route `GET /orders` | ⏳ PLANNED |
| T003-04 | Route `PATCH /orders/{orderId}/status` | ⏳ PLANNED |
| T003-05 | JWT-Autorisator (Cognito) anbinden | ⏳ PLANNED |
| T003-06 | Lambda-Invoke-Permission (Resource-Based Policy) | ⏳ PLANNED |
| T003-07 | Live-Test: alle Routen mit Token | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform validate/plan | NOT RUN |
| Live: Routen erreichbar (200) | NOT RUN |
| Live: 401 ohne Token | NOT RUN |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen

## Next Step

T003-01 (API + erste Route) — nach Freigabe.