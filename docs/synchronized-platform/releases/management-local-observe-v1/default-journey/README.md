# Corrected default Portal journey — 2026-11-06

The user reported a valid acceptance gap. The previous browser checks logged in but then opened an explicit entity URL and the Reliability page. They did not establish that the normal landing or bare Observe showed data. The [baseline](baseline.json) reproduced `/` → login → `/control` with an unavailable unselected factory, and bare `/observe` with zero entities and edges because only a handshake was requested.

Portal revision `7526fb1c32a745617c2e0b8d3c1ebbb9ff33edc2` corrects this within `management-local-observe-v1`:

- Natural sign-in lands on `/observe`, which requests the authenticated workspace's default owner-served slice.
- Both tenant sessions display three entities and two edges from their separate seeded Omniscience workspaces. Foreign-workspace reads are refused.
- The graph is labeled prepared synthetic topology. Live component state, cases, evidence and recommendations remain in Local Reliability.
- Control explicitly identifies factories as unselected; legacy profiles keep their factory behavior. Unselected Sentinel/DORA panels are omitted in this profile.
- Actual Omniscience loss renders an unconfirmed graph with no rows. Service readiness and both natural login journeys recovered after restart.

[Verification receipt](verification.json), [healthy browser run after recovery](browser.txt), [actual knowledge outage](knowledge-outage.txt), [final owner/UI observations](result.json).

Screenshots: [Observe alpha](observe-alpha.png), [Observe beta](observe-beta.png), [Control](control-after.png), [case evidence and recommendation](reliability-after.png). Original screenshots: [Control before](control-before.png), [Observe before](observe-before.png).

The initial qualification receipt and its manifest are unchanged historical evidence. This additive receipt corrects the scope of the prior completion claim; it does not claim a new full qualification of every component or a fresh model run. The local source images were rebuilt and activated; no PR was merged and no production or published-image release occurred.
