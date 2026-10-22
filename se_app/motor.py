"""Puente entre la aplicacion y el motor de inferencia en SWI-Prolog.

Usa Janus (janus_swi), que ejecuta Prolog dentro del mismo proceso de
Python. Aqui no se razona: solo se cargan los hechos en Prolog y se
traducen sus respuestas. Toda la logica de inferencia esta en
prolog/motor.pl (RNF26).
"""
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from . import config

_bin = Path(config.SWIPL_HOME) / "bin"
if os.name == "nt" and _bin.exists():
    os.add_dll_directory(str(_bin))
    os.environ.setdefault("SWI_HOME_DIR", config.SWIPL_HOME)

import janus_swi as janus  # noqa: E402  (requiere la ruta de las DLL)

janus.consult(str(config.MOTOR_PL))

# Janus admite hilos, pero el motor guarda la base en hechos dinamicos;
# un candado evita leer mientras otro hilo la recarga.
_candado = threading.Lock()


@dataclass
class Paso:
    tipo: str                 # 'pregunta' | 'diagnostico' | 'ninguno'
    codigo: str | None


@dataclass
class Base:
    """Copia en Python de la base cargada, para mostrar textos y metadatos."""
    categorias: list[dict] = field(default_factory=list)
    preguntas: dict[str, dict] = field(default_factory=dict)
    hipotesis: dict[str, dict] = field(default_factory=dict)

    def categoria(self, codigo: str) -> dict | None:
        return next((c for c in self.categorias if c["codigo"] == codigo), None)


base = Base()


def cargar(kb: dict) -> int:
    """Convierte la base leida de MySQL en hechos Prolog. Devuelve el numero de reglas."""
    preguntas = [(p["codigo"], p["categoria"], p["texto_pregunta"],
                  p["enunciado_positivo"], p["enunciado_negativo"]) for p in kb["preguntas"]]
    hipotesis = [(h["codigo"], h["categoria"], h["diagnostico"], h["nivel_urgencia"],
                  int(h["factor_certeza"]), h["especialista"], h["accion_recomendada"],
                  int(h["validada"])) for h in kb["hipotesis"]]
    condiciones = [(c["hipotesis"], c["pregunta"], int(c["valor_respuesta"]), int(c["orden"]))
                   for c in kb["condiciones"]]
    with _candado:
        janus.query_once("motor:cargar(P, H, C)", {"P": preguntas, "H": hipotesis, "C": condiciones})
        base.categorias = list(kb["categorias"])
        base.preguntas = {p["codigo"]: p for p in kb["preguntas"]}
        base.hipotesis = {h["codigo"]: h for h in kb["hipotesis"]}
        return janus.query_once("motor:total_reglas(N)")["N"]


def recargar() -> int:
    """Vuelve a leer la base de MySQL; se llama al iniciar y tras cada cambio del experto."""
    from . import conocimiento
    return cargar(conocimiento.leer_base())


def _hechos(respuestas) -> list[tuple[str, int]]:
    return [(codigo, int(valor)) for codigo, valor in respuestas]


def paso(categoria: str, respuestas) -> Paso:
    """Un ciclo de inferencia: siguiente pregunta, diagnostico o conclusion por defecto."""
    with _candado:
        r = janus.query_once("motor:paso(C, R, T, X)", {"C": categoria, "R": _hechos(respuestas)})
    return Paso(r["T"], r["X"] or None)


def estados(categoria: str, respuestas) -> dict[str, str]:
    """Estado de cada regla de la categoria: descartada, confirmada o en_evaluacion."""
    with _candado:
        r = janus.query_once("motor:estado_hipotesis(C, R, E)",
                             {"C": categoria, "R": _hechos(respuestas)})
    return {h: e for h, e in r["E"]}


def arbol(categoria: str, respuestas: tuple = ()) -> dict:
    """Arbol de decision de la categoria, tal como lo recorre el motor.

    No se dibuja a mano: se simulan las dos respuestas posibles a cada
    pregunta que formula el motor, de modo que el arbol siempre refleja la
    base de conocimiento cargada. Cada nodo es una pregunta con ramas
    'si' y 'no', o una hoja ('diagnostico' o 'ninguno').
    """
    p = paso(categoria, list(respuestas))
    if p.tipo != "pregunta":
        return {"tipo": p.tipo, "codigo": p.codigo}
    return {"tipo": "pregunta", "codigo": p.codigo,
            "si": arbol(categoria, respuestas + ((p.codigo, 1),)),
            "no": arbol(categoria, respuestas + ((p.codigo, 0),))}


def explicacion(hipotesis: str) -> list[tuple[str, int]]:
    """Ruta If / And de la regla: [(pregunta, valor esperado), ...]."""
    with _candado:
        r = janus.query_once("motor:explicacion(H, P)", {"H": hipotesis})
    return [(p, v) for p, v in r["P"]]
