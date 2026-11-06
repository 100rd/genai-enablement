# Barbarossa work in Control

Verified and running locally at Portal `1389aae9112ba03696fb3bc99560e970887d3241` and Barbarossa `1c6335656b348dbd9025aa82d0cb730b442604dd`.

Control now contains cases, runner heartbeat/errors, the actual analysis queue and terminal history,
and exact accepted job results with text recommendations. Observe retains observations, tenant
knowledge and recorded case evidence. Existing evidence bookmarks link to Control case results.

The lead ran the real Chromium journeys: **4 passed**, with two outage-only tests explicitly skipped.
Both tenant logins and graph boundaries passed; the allowed tenant sees work and the other receives
an explicit denial. Manual refresh changed the database snapshot. A selected job showed its exact
accepted recommendations and linked to recorded evidence in Observe, then back to its Control case.
See [verification](verification.json), [browser output](browser.txt), [Control screenshot](control.png),
[assessment screenshot](assessment.png) and [Observe screenshot](observe.png).

The backend rollout itself was observed as a Portal outage. Barbarossa opened a new case, Codex
completed one additional analysis, and recovery was recorded. The final state is **6 cases, 6 jobs,
4 accepted assessments, 6 durable launch reservations, an empty queue, and an online runner**.
This was an automatic consequence of backend recreation, not a new deliberately scheduled drill.
[Live API checks](live-api.json) record exact accepted results and negative identity tests.

[Reviews and execution notes](reviews.json) disclose fixes, estimates and verification retries,
including premature browser startup and a cold graph exceeding the old five-second test assertion.
The lead repeated all 10 disposable PostgreSQL tests, 22 focused proxy tests and all 682 frontend
tests. Existing histories and volumes were preserved. Historical receipts retain their original
meaning; image publication, execution, production and HA remain separate work.
