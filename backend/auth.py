"""Auth via oauth2-proxy central (SSO M365).

O edge (Traefik forwardauth -> https://auth.soarespicon.adv.br/oauth2/auth) valida
a sessao M365 e injeta os headers `X-Auth-Request-*`. Este modulo APENAS os le
(fail-closed). Espelha o kit do lancador-sp-apps (app/auth/headers.py + roles.py).

Login local foi REMOVIDO (JWT hardcoded + users.json) — a unica porta agora e o SSO.

Anti-spoof (WP-SEC2): o container escuta na rede `coolify` compartilhada com
dezenas de apps, entao X-Auth-Request-Email sozinho e forjavel por qualquer
vizinho falando direto com :8000, contornando o oauth2-proxy/Traefik
inteiramente. Quando PROXY_SHARED_SECRET esta setado, o Traefik injeta
X-Proxy-Secret (customRequestHeaders via @file) no router protegido do PDF e
aqui exigimos o match ANTES de confiar em qualquer header de identidade —
requisicao que nao passou pelo proxy recebe 401. Env vazia = comportamento
antigo (dev/local sem proxy). Mesma mecanica do sp-copiloto/laudo/sp-painel-prazos.
"""
from __future__ import annotations

import hmac
import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
# DEV_BYPASS_AUTH=1 injeta usuario mock local (sem oauth2-proxy). Proibido em producao.
DEV_BYPASS_AUTH = os.getenv("DEV_BYPASS_AUTH", "").strip().lower() in {"1", "true", "yes"}
# Override de papel por email: "email1=role1,email2=roleA+roleB"
SSO_EMAIL_ROLE_MAP = os.getenv("SSO_EMAIL_ROLE_MAP", "")

# [fail-safe] espelha portal-api/lancador: o app NAO sobe com bypass em producao.
if DEV_BYPASS_AUTH and ENVIRONMENT == "production":
    raise RuntimeError(
        "DEV_BYPASS_AUTH com ENVIRONMENT=production e proibido — o app nao sobe."
    )

# Precedencia de papel (maior privilegio primeiro), p/ resolver o campo `role`.
_ROLE_PRECEDENCE = ("admin", "socio", "gestora", "advogado", "administrativo", "comunicacao")


def _email_role_overrides() -> dict[str, set[str]]:
    """Parseia SSO_EMAIL_ROLE_MAP -> {email: {roles}}."""
    out: dict[str, set[str]] = {}
    for pair in (SSO_EMAIL_ROLE_MAP or "").split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        email, spec = pair.split("=", 1)
        email = email.strip().lower()
        roles = {r.strip() for r in spec.split("+") if r.strip()}
        if email and roles:
            out.setdefault(email, set()).update(roles)
    return out


_OVERRIDES = _email_role_overrides()
logger.info("SSO auth ativo (env=%s, bypass=%s, %d overrides)", ENVIRONMENT, DEV_BYPASS_AUTH, len(_OVERRIDES))


def _role_for(email: str) -> str:
    """Papel efetivo (string unica) p/ o campo `role` da UI. Default 'user'."""
    roles = _OVERRIDES.get((email or "").lower())
    if not roles:
        return "user"
    for r in _ROLE_PRECEDENCE:
        if r in roles:
            return r
    return next(iter(roles))


async def get_current_user(
    email: str | None = Header(None, alias="X-Auth-Request-Email"),
    oid: str | None = Header(None, alias="X-Auth-Request-User"),
    preferred: str | None = Header(None, alias="X-Auth-Request-Preferred-Username"),
    proxy_secret: str | None = Header(None, alias="X-Proxy-Secret"),
) -> dict:
    """Le os headers do oauth2-proxy -> {email, name, role}. 401 se ausentes."""
    if DEV_BYPASS_AUTH and not email:
        return {"email": "dev@soarespicon.adv.br", "name": "Dev (bypass)", "role": "admin"}

    # Anti-spoof (WP-SEC2): exige o segredo injetado pelo Traefik ANTES de
    # confiar em qualquer header de identidade. Roda mesmo se `email` vier
    # vazio, para nao vazar info sobre o estado do gate.
    secret = os.environ.get("PROXY_SHARED_SECRET", "")
    if secret and not (proxy_secret and hmac.compare_digest(proxy_secret, secret)):
        raise HTTPException(
            status_code=401,
            detail="A requisição não passou pelo proxy",
        )

    if not email:
        # oauth2-proxy upstream nao configurado/headers ausentes -> 401 explicito.
        raise HTTPException(
            status_code=401,
            detail="auth headers ausentes — oauth2-proxy upstream nao esta configurado",
        )
    name = preferred or email.split("@")[0]
    return {"email": email, "name": name, "role": _role_for(email)}
