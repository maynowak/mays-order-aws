# MO-RC4-P00-G — Retention / TTL bleibt entscheidungsbedingt deaktiviert

**Status:** `BLOCKED BY OWNER DECISION / SAFELY DISABLED`
**Datum:** 2026-11-14

## Entscheidung

P00-G wird in RC4 nicht implementiert. Es werden keine `retentionUntil`-,
`ttl`-, `retentionPolicy`- oder `tenantId`-Felder eingeführt, keine TTL
konfiguriert und keine automatische Löschung aktiviert.

## Begründung

Folgende Owner-/Rechtsentscheidungen sind nicht getroffen:

- **Q-05:** `tenantId` optional/erforderlich?
- **Q-06:** fachliche Aufbewahrungsfristen; keine Frist ist freigegeben.
- **Q-07:** Cancel-Anonymisierung sofort, wartend oder opt-in?
- **Q-14:** Umgang mit Bestandsdaten ohne Retention; kein automatischer Backfill.

Der bestehende Vertrag bezeichnet `retentionUntil` und `ttl` ausdrücklich als
Vorschlag, nicht als freigegeben. TTL ist asynchron und keine Löschgarantie.
Eine Implementierung ohne diese Entscheidungen würde Fristen oder
Löschsemantik erfinden.

## Sicherheitsgrenze

- ERASE/ANONYMIZE/RETAIN bleiben unverändert und require weiterhin eine
  explizite Policy.
- Keine automatische Löschung, kein Backfill, kein stiller Default.
- Keine Änderung an DynamoDB-TTL, Terraform oder Bestandsdaten.
- Keine Aussage über DSGVO-Konformität oder Löschfristen.

## Nächster Schritt

Q-05/Q-06/Q-07/Q-14 durch den Owner entscheiden. Erst danach kann P00-G als
eigener, freigegebener Implementierungsschritt folgen.
