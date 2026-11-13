# MO-RIS-AGENT-ORDER-BODY-01 — A04 Nested Agent Order Body (Create & Persistence)

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Tests (keine AWS-Mutation, kein Deployment)
**Ergebnis:** A04 COMPLETE. Ein `agentOrder` V1 wird validiert angenommen,
als eigener Bestandteil persistiert und **nicht** öffentlich ausgegeben.

## 1. Zielbasis und Reconciliation

| Prüfung | Ergebnis |
|---|---|
| Zielbranch | `feature/mo-agent-order-body-01`, gestartet von `9627eb2` |
| `5cf50a0` (RIS-Pin, v0.5.0-rc.2) → `9627eb2` | **Vorfahr**; `git diff 5cf50a0 9627eb2 -- lambda/src` ist **leer** |
| `9627eb2` → `origin/main` | **Vorfahr** (RC4 fügt Dateien hinzu, entfernt keine) |
| Arbeitsbaum vor Start | clean; fremder Checkout blieb unberührt (eigener Worktree) |

**Korrektur des A00-Befunds.** A00 behauptete, `orderType`, `identity.py`,
`order_handlers.py` und `processing_result.py` existierten nicht. Das war falsch,
weil `origin/main` im lokalen Clone **veraltet** war. Nach `git fetch` steht
`origin/main` auf `f597d14` und enthält genau diese Bausteine — sie gehören zur
**RC4-Linie**, nicht zur getesteten Basis.

Damit gilt:

- Der Auftrag beschreibt korrekt die RC4-Features.
- Die **getestete Integrationsbasis** ist die RC2-/Modul-Contract-Linie
  (`5cf50a0` ≡ `9627eb2` im Lambda-Code).
- Es findet **keine RC-Migration** statt; implementiert wird auf der getesteten
  Linie. RC4 bleibt unangetastet.

## 2. Tatsächlich vorhandene Komponenten auf der Zielbasis

| Komponente | Vorhanden | Konsequenz für A04 |
|---|---|---|
| `POST /orders` mit strikter Allowlist | ja | erweitert |
| `orderType` | nein | eingeführt, nur `agent.execution` |
| Handler-Registry | nein | A05, nicht A04 |
| Processing-State / Result-Persistenz | nein | A06, nicht A04 |
| Eigentümerbindung | **nein** | A04.5: `agentOrder` bleibt intern |
| Retail-Lifecycle, Statusmodell | ja | unverändert |

## 3. Änderungen

| Datei | Inhalt |
|---|---|
| `lambda/src/agent_order.py` | neu: V1-Validator, Fingerprint, stabile Fehlercodes |
| `lambda/src/validation.py` | optionaler Agent-Zweig, gegenseitiger Ausschluss zu Retail |
| `lambda/src/order_service.py` | `_create_agent_order`, interne Felder, Listenprojektion |
| `lambda/src/index.py` | kein SQS-Dispatch für Agent-Orders |
| `lambda/tests/test_agent_order.py` | neu: 20 Tests |

## 4. Validierungsvertrag

Akzeptiert: `orderType: "agent.execution"` + `agentOrder` (V1, `schemaVersion`
`"1.0"`/`"1"`). Abgelehnt mit `400 VALIDATION_ERROR`:

- `agentOrder` ohne `orderType` und umgekehrt
- `orderType` ≠ `agent.execution`
- Kombination mit `customer`/`items`/`currency`
- unbekannte Felder auf jeder Ebene, unbekannte Versionen
- ungültige Capability, `resultContract`-Widerspruch
- Secret-förmige Schlüssel/Werte (`ris_`, `Bearer `), > 16 KiB

**Retail bleibt unverändert:** ohne `orderType`/`agentOrder` läuft exakt der
bisherige Pfad.

Die Validierung ist eine bewusste, begrenzte Duplikation des RIS-Contracts
(separate Deployables, kein Cross-Repo-Import). Schema-Version und Fehlercodes
sind auf beiden Seiten identisch; die RIS-Suite nutzt dieselben Fixtures.

## 5. Persistenz

```json
{
  "pk": "ord_…", "sk": "#ORDER", "orderId": "ord_…",
  "orderType": "agent.execution",
  "status": "PENDING",
  "agentOrder": { … validiert … },
  "agentOrderFingerprint": "sha256(schemaVersion+target+input)",
  "createdAt": "…", "updatedAt": "…", "version": 1,
  "gsi1pk": "LIST", "gsi1sk": "…"
}
```

- kein `customer`, `items`, `currency`, `totalAmount` — **keine erfundenen
  Retail-Positionen**
- bestehende `orderId`-Erzeugung, Zeitstempel, `version`, GSI1 unverändert
- Fingerprint macht eine stille Änderung der angenommenen Ausführungsparameter
  nachweisbar; Korrelationsfelder sind ausgenommen

## 6. Datenschutz und Identität (A04.5)

Die Zielbasis hat **keine** Eigentümerprüfung. Deshalb:

- `agentOrder` und `agentOrderFingerprint` stehen in `INTERNAL_FIELDS` und
  erscheinen **nicht** in `GET /orders/{id}`.
- Die Listenprojektion für Agent-Orders ist minimal (`orderId`, `orderType`,
  `status`, `createdAt`, `updatedAt`) — kein Kunde, kein Betrag, kein Body.
- Kein neuer öffentlicher Datenzugriff entsteht: die sichtbaren Felder sind
  dieselben, die jede Retail-Order heute schon zeigt.
- Agent-Orders werden **nicht** an den Retail-SQS-Worker gesendet; der
  status-only Consumer würde ihren Lifecycle verfälschen.

Der autorisierte Auftraggeberzugriff bleibt einem separaten Sicherheits-Gate
vorbehalten.

## 7. Tests

`cd lambda && PYTHONPATH=src python -m unittest discover -s tests`
→ **96 Tests, OK** (76 bestehende + 20 neue), `compileall` sauber.

Neue Abdeckung: gültig/minimal/Version `1`, unbekannte Version, unbekannte
Felder, gegenseitiger Ausschluss, fremder `orderType`, Retail-Regression,
Secret-Ablehnung ohne Secret im Fehlertext, Größenlimit, Fingerprint;
Persistenz ohne Retail-Felder, interne Projektion, minimale Listenprojektion,
unveränderte Retail-Persistenz; HTTP-Route ohne SQS für Agent-Orders und
mit SQS für Retail.

## 8. Verbleibende Blocker

| Punkt | Status |
|---|---|
| Eigentümerbindung / autorisierter Abruf | **separates Sicherheits-Gate** |
| A05 Orders→RIS Dispatch | offen (kein Consumer) |
| A06 RIS→Orders Result | offen (keine Result-Persistenz) |
| A07 Voll-E2E | offen |

Kein Live-Pfad, kein Deployment, keine RC-Migration.
