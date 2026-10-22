"""Pruebas del motor de inferencia (objetivo 4: validacion).

- Pruebas unitarias con una base minima, sin MySQL.
- Validacion completa contra la base real (se omite si MySQL no responde):
  recorre la ruta de cada una de las reglas y los casos de prueba de la
  Tabla 52 del manual.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from se_app import conocimiento, db, motor  # noqa: E402


def _base_minima():
    def h(cod, urg, fc):
        return {"codigo": cod, "categoria": "ELE", "diagnostico": cod, "nivel_urgencia": urg, "factor_certeza": fc,
                "especialista": "x", "accion_recomendada": "y", "validada": 1}
    reglas = {
        "E05": [("olor_quemado", 1), ("sobrecalentamiento", 1)],
        "E01": [("olor_quemado", 1), ("sobrecalentamiento", 0), ("breaker", 1)],
        "E08": [("olor_quemado", 1), ("sobrecalentamiento", 0), ("breaker", 0)],
        "E02": [("olor_quemado", 0), ("chispas", 1)],
    }
    return {
        "categorias": [{"codigo": "ELE", "nombre": "Eléctrica"}],
        "preguntas": [{"codigo": c, "categoria": "ELE", "texto_pregunta": c, "enunciado_positivo": c,
                       "enunciado_negativo": "no " + c} for c in ("olor_quemado", "sobrecalentamiento", "breaker", "chispas")],
        "hipotesis": [h("E05", "Critica", 93), h("E01", "Alta", 88), h("E08", "Alta", 76), h("E02", "Critica", 92)],
        "condiciones": [{"hipotesis": hc, "pregunta": p, "valor_respuesta": v, "orden": i + 1}
                        for hc, conds in reglas.items() for i, (p, v) in enumerate(conds)],
    }


def recorrer(categoria, contestar, limite=40):
    """Simula al usuario: responde lo que el motor pregunte hasta que concluya."""
    respuestas = []
    for _ in range(limite):
        paso = motor.paso(categoria, respuestas)
        if paso.tipo != "pregunta":
            return paso, respuestas
        respuestas.append((paso.codigo, contestar(paso.codigo)))
    raise AssertionError("El motor no llegó a una conclusión")


# ---------------------------------------------------------------- unitarias

class TestMotorUnitario:
    @pytest.fixture(autouse=True)
    def cargar(self):
        motor.cargar(_base_minima())
        yield
        if db.disponible():
            motor.recargar()

    def test_primera_pregunta_es_la_raiz_del_arbol(self):
        assert motor.paso("ELE", []) == motor.Paso("pregunta", "olor_quemado")

    def test_solo_pregunta_lo_necesario(self):
        paso, resp = recorrer("ELE", lambda p: 1)
        assert paso == motor.Paso("diagnostico", "E05")
        assert [p for p, _ in resp] == ["olor_quemado", "sobrecalentamiento"]

    def test_rama_negativa(self):
        paso, _ = recorrer("ELE", {"olor_quemado": 1, "sobrecalentamiento": 0, "breaker": 1}.get)
        assert paso.codigo == "E01"

    def test_conclusion_por_defecto(self):
        paso, _ = recorrer("ELE", lambda p: 0)
        assert paso == motor.Paso("ninguno", None)

    def test_estados_descartan_reglas_contradichas(self):
        estados = motor.estados("ELE", [("olor_quemado", 1)])
        assert estados["E02"] == "descartada"
        assert estados["E05"] == "en_evaluacion"

    def test_explicacion_en_orden(self):
        assert motor.explicacion("E01") == [("olor_quemado", 1), ("sobrecalentamiento", 0), ("breaker", 1)]


# ---------------------------------------------------------------- base real

requiere_mysql = pytest.mark.skipif(not db.disponible(), reason="MySQL no disponible")


@pytest.fixture(scope="module")
def base_real():
    kb = conocimiento.leer_base()
    motor.cargar(kb)
    return kb


def _reglas(kb):
    conds = {}
    for c in kb["condiciones"]:
        conds.setdefault(c["hipotesis"], {})[c["pregunta"]] = c["valor_respuesta"]
    return [(h["codigo"], h["categoria"], conds.get(h["codigo"], {})) for h in kb["hipotesis"]]


@requiere_mysql
def test_cada_regla_se_alcanza_por_su_ruta(base_real):
    """Respondiendo segun las condiciones de cada regla, el motor la concluye."""
    fallas = []
    for codigo, categoria, condiciones in _reglas(base_real):
        paso, _ = recorrer(categoria, lambda p: condiciones.get(p, 0))
        if paso.codigo != codigo:
            fallas.append(f"{codigo}: concluyó {paso.codigo}")
    assert not fallas, fallas


CASOS_TABLA_52 = [
    ("CP01", "ELE", {"olor_quemado": 1, "sobrecalentamiento": 1}, "E05"),
    ("CP02", "ELE", {"olor_quemado": 1, "breaker": 1, "sobrecalentamiento": 0}, "E01"),
    ("CP06", "EST", None, "S03"),
    ("CP09", "GAS", {"olor_gas": 1, "silbido": 0}, "G04"),
]


@requiere_mysql
@pytest.mark.parametrize("caso,categoria,respuestas,esperado", CASOS_TABLA_52)
def test_casos_de_prueba_del_manual(base_real, caso, categoria, respuestas, esperado):
    if respuestas is None:
        respuestas = dict(next(c for h, _, c in _reglas(base_real) if h == esperado))
    paso, _ = recorrer(categoria, lambda p: respuestas.get(p, 0))
    assert paso.codigo == esperado, caso


@requiere_mysql
def test_arboles_cubren_todas_las_reglas(base_real):
    """Cada regla es exactamente una hoja de su arbol, mas una conclusion por defecto por categoria."""
    def hojas(n):
        return [n["codigo"]] if n["tipo"] != "pregunta" else hojas(n["si"]) + hojas(n["no"])
    todas = []
    for c in base_real["categorias"]:
        h = hojas(motor.arbol(c["codigo"]))
        assert h.count(None) == 1, c["codigo"]
        todas += [x for x in h if x]
    assert sorted(todas) == sorted(h["codigo"] for h in base_real["hipotesis"])
