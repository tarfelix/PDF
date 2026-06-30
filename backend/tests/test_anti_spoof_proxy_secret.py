"""WP-SEC2 — anti-spoof do header SSO via X-Proxy-Secret.

O backend escuta na rede `coolify` compartilhada; sem o gate de segredo,
qualquer container vizinho forja X-Auth-Request-Email falando direto com
:8000 e impersona qualquer usuário (contorna o oauth2-proxy/Traefik). Estes
testes provam que:
  - com PROXY_SHARED_SECRET setado, requisição SEM o X-Proxy-Secret correto é
    rejeitada com 401;
  - com o segredo correto, o fluxo normal de auth prossegue;
  - com PROXY_SHARED_SECRET vazio, o comportamento antigo é preservado (dev).

Exercita `get_current_user` REAL (sem mocks de FastAPI) — é o caminho que a
correção endurece. Espelha sp-painel-prazos/backend/tests/api/test_anti_spoof_proxy_secret.py.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from auth import get_current_user

SECRET = "s3cr3t-do-traefik"


async def test_forged_sem_secret_rejeitado(monkeypatch):
    """Header forjado por container interno, sem X-Proxy-Secret -> 401."""
    monkeypatch.setenv("PROXY_SHARED_SECRET", SECRET)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            email="attacker-forged@soarespicon.adv.br",
            oid=None,
            preferred=None,
            proxy_secret=None,
        )
    assert exc.value.status_code == 401


async def test_secret_errado_rejeitado(monkeypatch):
    monkeypatch.setenv("PROXY_SHARED_SECRET", SECRET)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            email="attacker-forged@soarespicon.adv.br",
            oid=None,
            preferred=None,
            proxy_secret="palpite-errado",
        )
    assert exc.value.status_code == 401


async def test_secret_correto_passa(monkeypatch):
    """Requisição legítima vinda do proxy (segredo certo) prossegue normalmente."""
    monkeypatch.setenv("PROXY_SHARED_SECRET", SECRET)

    out = await get_current_user(
        email="tarcisio@soarespicon.adv.br",
        oid="oid-123",
        preferred="tarcisio.picon",
        proxy_secret=SECRET,
    )
    assert out["email"] == "tarcisio@soarespicon.adv.br"


async def test_sem_secret_configurado_preserva_comportamento_antigo(monkeypatch):
    """PROXY_SHARED_SECRET vazio = dev/local sem proxy: não exige X-Proxy-Secret."""
    monkeypatch.setenv("PROXY_SHARED_SECRET", "")

    out = await get_current_user(
        email="tarcisio@soarespicon.adv.br",
        oid=None,
        preferred=None,
        proxy_secret=None,
    )
    assert out["email"] == "tarcisio@soarespicon.adv.br"


async def test_sem_email_continua_401_com_secret_correto(monkeypatch):
    """Segredo correto não dispensa o header de identidade — ausência de email ainda é 401."""
    monkeypatch.setenv("PROXY_SHARED_SECRET", SECRET)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            email=None,
            oid=None,
            preferred=None,
            proxy_secret=SECRET,
        )
    assert exc.value.status_code == 401
