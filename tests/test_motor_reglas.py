"""Pruebas del motor de reglas simbolico en Prolog (arbol de decision y confirmacion de reglas).

- Unitarias con una base minima en memoria, sin MySQL.
- Contra la base real (se omiten si MySQL no responde): el arbol de cada
  categoria cubre todas las reglas.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from se_app.contenedor import contenedor  # noqa: E402
from se_app.negocio.motor_prolog import MotorProlog  # noqa: E402
from tests.base_prueba import RepositorioEnMemoria  # noqa: E402

requiere_mysql = pytest.mark.skipif(not contenedor.bd.disponible(), reason="MySQL no disponible")


def recorrer(motor, categoria, contestar, limite=40):
    """Simula al usuario: responde lo que el motor de reglas pregunte hasta que concluya."""
    respuestas = []
    for _ in range(limite):
        tipo, codigo = motor.paso(categoria, respuestas)
        if tipo != "pregunta":
            return (tipo, codigo), respuestas
        respuestas.append((codigo, contestar(codigo)))
    raise AssertionError("El motor no llegó a una conclusión")


class TestMotorPrologUnitario:
    @pytest.fixture
    def motor(self):
        m = MotorProlog(RepositorioEnMemoria())
        m.recargar()
        yield m
        if contenedor.bd.disponible():       # deja cargada la base real para las demas pruebas
            contenedor.motor_prolog.recargar()

    def test_primera_pregunta_es_la_raiz_del_arbol(self, motor):
        assert motor.paso("ELE", []) == ("pregunta", "olor_quemado")

    def test_solo_pregunta_lo_necesario(self, motor):
        fin, resp = recorrer(motor, "ELE", lambda p: 1)
        assert fin == ("diagnostico", "E05")
        assert [p for p, _ in resp] == ["olor_quemado", "sobrecalentamiento"]

    def test_conclusion_por_defecto(self, motor):
        fin, _ = recorrer(motor, "ELE", lambda p: 0)
        assert fin == ("ninguno", None)

    def test_confirma_solo_reglas_que_se_cumplen(self, motor):
        respuestas = [("olor_quemado", 1), ("sobrecalentamiento", 1)]
        assert motor.confirma("ELE", respuestas, "E05")
        assert not motor.confirma("ELE", respuestas, "E01")

    def test_explicacion_en_orden(self, motor):
        assert motor.explicacion("E01") == [("olor_quemado", 1), ("sobrecalentamiento", 0), ("breaker", 1)]


@requiere_mysql
def test_arboles_cubren_todas_las_reglas():
    """Cada regla es exactamente una hoja de su arbol, mas una conclusion por defecto por categoria."""
    motor = contenedor.motor_prolog
    kb = contenedor.repo_conocimiento.leer_base()
    motor.cargar(kb)

    def hojas(n):
        return [n["codigo"]] if n["tipo"] != "pregunta" else hojas(n["si"]) + hojas(n["no"])
    todas = []
    for c in kb["categorias"]:
        h = hojas(motor.arbol(c["codigo"]))
        assert h.count(None) == 1, c["codigo"]
        todas += [x for x in h if x]
    assert sorted(todas) == sorted(h["codigo"] for h in kb["hipotesis"])
