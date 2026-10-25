"""Pruebas del registro publico y del alta de usuarios (requieren MySQL)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from se_app.contenedor import contenedor  # noqa: E402
from se_app.main import app  # noqa: E402

db = contenedor.bd

pytestmark = pytest.mark.skipif(not db.disponible(), reason="MySQL no disponible")

NUEVO = {"nombres": "Prueba", "apellidos": "Automática", "tipo_documento": "CC", "numero_documento": "70000001",
         "correo": "prueba.auto@ejemplo.test", "telefono": "", "usuario": "prueba.auto",
         "contrasena": "Registro2026", "confirmacion": "Registro2026"}


@pytest.fixture
def cliente():
    yield TestClient(app)
    db.ejecutar("DELETE FROM usuario WHERE usuario = %s", (NUEVO["usuario"],))


def test_registro_valida_campos(cliente):
    r = cliente.post("/registro", data={**NUEVO, "correo": "malo", "usuario": "consulta", "confirmacion": "otra"})
    assert r.status_code == 200
    assert "El correo no tiene un formato válido." in r.text
    assert "Ese nombre de usuario ya está en uso." in r.text
    assert "Las contraseñas no coinciden." in r.text
    assert not db.consultar_uno("SELECT 1 AS x FROM usuario WHERE correo = 'malo'")


def test_registro_crea_consultante_e_inicia_sesion(cliente):
    r = cliente.post("/registro", data={**NUEVO, "rol": "ADMINISTRADOR"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/viviendas")
    fila = db.consultar_uno("SELECT rol, contrasena_hash FROM usuario WHERE usuario = %s", (NUEVO["usuario"],))
    assert fila["rol"] == "CONSULTANTE"          # el registro publico no permite elegir rol
    assert fila["contrasena_hash"].startswith("scrypt$")
    assert cliente.get("/viviendas").status_code == 200


def test_solo_el_administrador_crea_usuarios(cliente):
    r = cliente.post("/usuarios", data={**NUEVO, "rol": "EXPERTO"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert not db.consultar_uno("SELECT 1 AS x FROM usuario WHERE usuario = %s", (NUEVO["usuario"],))
