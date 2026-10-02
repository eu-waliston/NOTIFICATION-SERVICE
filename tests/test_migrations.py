import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[1]


def _alembic(*args, db):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True)


def test_migrations_apply_and_match_models():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "m.db"
        up = _alembic("upgrade", "head", db=db)
        assert up.returncode == 0, up.stderr
        tables = set(inspect(create_engine(f"sqlite:///{db}")).get_table_names())
        assert {"notifications", "templates", "api_clients", "audit_logs"} <= tables
        # `alembic check` falha se os modelos divergirem das migrações
        chk = _alembic("check", db=db)
        assert chk.returncode == 0, chk.stdout + chk.stderr
