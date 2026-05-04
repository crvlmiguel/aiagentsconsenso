"""Shared pytest configuration — carrega REACT_APP_BACKEND_URL do frontend/.env.

Os testes de integração apontam para o backend HTTPS público (mesmo URL que o
frontend usa). Isto evita ter de exportar variáveis manualmente no shell.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega frontend/.env (REACT_APP_BACKEND_URL) e backend/.env como fallback
_FRONTEND_ENV = Path(__file__).resolve().parents[2] / "frontend" / ".env"
_BACKEND_ENV = Path(__file__).resolve().parents[1] / ".env"
for p in (_FRONTEND_ENV, _BACKEND_ENV):
    if p.exists():
        load_dotenv(p, override=False)

# Sanity check — falha rápido se ainda em falta
if not os.environ.get("REACT_APP_BACKEND_URL"):
    raise RuntimeError(
        f"REACT_APP_BACKEND_URL not found. Procurei em {_FRONTEND_ENV} e {_BACKEND_ENV}."
    )
