# MAYS-ORDERS-PRIVACY-TRUST-FIX-01

## Root Cause
`_require_privacy_auth` übersprang Tokenprüfung, wenn `PRIVACY_INTERNAL_SECRET` nicht gesetzt war. Das ermöglichte eine Scheinsicherheit: fehlendes Secret deaktivierte die interne Vertrauensgrenze.

## Fix
- Secret muss gesetzt und nicht leer sein, sonst BLOCKED
- Token muss vorhanden sein und via `secrets.compare_digest` gegen Secret geprüft werden
- Fehlender/ungerichtiger Token -> `validation_error`
- Konstante Zeitvergleiche verhindern Timing Attacks

## Trust Boundary
Interne Privacy-Operationen erfordern jetzt:
1. Projekt-Isolation
2. Permission-Flag
3. Authorized Flag
4. Korrekter `internal_token` == `PRIVACY_INTERNAL_SECRET`

Token wird über Umgebungsvariable bereitgestellt und muss von internem Code gesetzt werden. Keine Secrets in Tests/Logs.

## Tests
- Secret fehlt → Blocked
- Secret leer → Blocked
- Token fehlt → Blocked
- Token falsch → Blocked
- Token korrekt → Erlaubt
- Projekt falsch → Blocked
- Permission fehlt → Blocked

Alle Regressionstests grün.

## Review
Keine öffentlichen Endpunkte, keine neuen AWS-Ressourcen, keine Auth-Plattform. Vertrauensgrenze minimal aber erzwungen.

## Remaining Risks
Token wird als String übergeben, kann bei unsachgemäßer Weitergabe an Client sichtbar werden. Empfohlene Runtime-Vertrauensgrenze: Token nur innerhalb Lambda-Prozess setzen, nicht über HTTP.

## Empfehlung
Freigabe für Integrationstest. Für Production sollte Token über sicheren internen Mechanismus gesetzt werden, idealerweise nur aus Umgebung sichtbar für vertrauenswürdigen Codepfad.
