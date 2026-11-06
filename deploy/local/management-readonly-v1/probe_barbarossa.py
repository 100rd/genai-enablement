"""Fixed local availability probe executed inside the legacy Portal backend."""

import json
import os
from uuid import UUID

URL = "http://barbarossa-api:8080/v1/local/availability"
PROBE_USER = UUID("00000000-0000-0000-0000-00000000df01")


def probe(client, sign_for, tenant):
    unsigned = client.get(URL)
    allowed = {"Authorization": f"Bearer {sign_for(tenant)}"}
    signed = client.get(URL, headers=allowed)
    foreign_tenant = UUID(int=tenant.int ^ (1 << 127))
    foreign = client.get(
        URL, headers={"Authorization": f"Bearer {sign_for(foreign_tenant)}"}
    )
    scope_mismatch = client.get(
        URL, headers=allowed, params={"tenant": "tenant:qualification-foreign"}
    )
    valid_shape = False
    if signed.status_code == 200:
        try:
            body = signed.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and isinstance(body.get("topology"), dict):
            topology = body["topology"]
            valid_shape = (
                isinstance(body.get("availability"), dict)
                and topology.get("availability_class") == "development-single-host"
                and topology.get("ha_qualified") is False
                and topology.get("activation_authority") == "none"
            )
    return {
        "unsigned_status": unsigned.status_code,
        "signed_status": signed.status_code,
        "foreign_status": foreign.status_code,
        "scope_mismatch_status": scope_mismatch.status_code,
        "valid_shape": valid_shape,
    }


def main():
    import httpx

    from app.auth.principal import TenantPrincipal
    from app.local_observe.delegation import sign_read_token
    from app.rbac.roles import Role

    tenant = UUID(os.environ["PORTAL_LEGACY_READ_TENANT_ID"])

    def sign_for(tenant_id):
        # A fixed synthetic read principal for this local, container-only
        # qualifier. The browser and Portal routes still use server sessions.
        return sign_read_token(
            TenantPrincipal(PROBE_USER, tenant_id, (Role.TENANT_VIEWER,), False)
        )

    with httpx.Client(timeout=5.0, trust_env=False, follow_redirects=False) as client:
        print(json.dumps(probe(client, sign_for, tenant)))


if __name__ == "__main__":
    main()
