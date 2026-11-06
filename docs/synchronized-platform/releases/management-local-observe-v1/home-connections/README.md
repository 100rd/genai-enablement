# Home connection cards — 2026-11-06

Portal `ae74ebc39da2ebc558d509ac8a12ca98f0dc01f8` places Barbarossa and Omniscience connection/readiness cards at the top of the local landing page. Each displays the component's last readiness check in UTC. The cards read authenticated Barbarossa observations, refresh every 30 seconds, allow manual refresh, and stream independently of workspace knowledge.

[Home screenshot](home.png) · [Verification receipt](verification.json) · [Browser run](browser.txt) · [175 frontend checks](frontend-tests.txt) · [Independent-loading measurement](streaming.json).

Both real Keycloak sessions were checked: alpha sees its permitted observations; beta sees status access denied while its own knowledge remains readable. A simulated browser HTTP 503 removes old health readings and the next real BFF poll restores them. With the real Omniscience API briefly paused, the cards appeared after 853 ms while the graph was still pending. The API was resumed and a fresh page read returned its graph. The pause does not assert an immediate unhealthy readiness verdict: these are timestamped, debounced local probes.

Unit tests cover stale and missing data, failed readiness, timeout, denied access, invalid schemas, overlapping requests and late responses across tenant changes. TypeScript and generic code review findings were closed before acceptance. The local frontend source image was rebuilt and activated; backend/owner code and persistent volumes were unchanged. Historical qualification, default-journey correction and production/release boundaries retain their separate scope.
