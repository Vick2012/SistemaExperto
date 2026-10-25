"""Motor de reglas simbolico en SWI-Prolog (prolog/motor.pl), via Janus.

Complementa al motor bayesiano: dibuja el arbol de decision de cada
categoria, comprueba la coherencia de las reglas y confirma de forma
logica si la regla ganadora se cumple con las respuestas dadas.
"""
import os
import threading
from pathlib import Path

from .. import config

_bin = Path(config.SWIPL_HOME) / "bin"
if os.name == "nt" and _bin.exists():
    os.add_dll_directory(str(_bin))
    os.environ.setdefault("SWI_HOME_DIR", config.SWIPL_HOME)

import janus_swi as janus  # noqa: E402  (requiere la ruta de las DLL)

janus.consult(str(config.MOTOR_PL))


class MotorProlog:
    def __init__(self, repositorio):
        # repositorio: RepositorioConocimiento (capa de datos), inyectado.
        self.repositorio = repositorio
        # Janus admite hilos, pero el motor guarda la base en hechos dinamicos;
        # el candado evita consultar mientras otro hilo la recarga.
        self._candado = threading.Lock()
        self.categorias: list[dict] = []
        self.preguntas: dict[str, dict] = {}
        self.hipotesis: dict[str, dict] = {}

    @property
    def cargado(self) -> bool:
        return bool(self.categorias)

    def categoria(self, codigo: str) -> dict | None:
        return next((c for c in self.categorias if c["codigo"] == codigo), None)

    def cargar(self, kb: dict) -> int:
        """Convierte la base leida de MySQL en hechos Prolog. Devuelve el numero de reglas."""
        preguntas = [(p["codigo"], p["categoria"], p["texto_pregunta"], p["enunciado_positivo"],
                      p["enunciado_negativo"]) for p in kb["preguntas"]]
        hipotesis = [(h["codigo"], h["categoria"], h["diagnostico"], h["nivel_urgencia"], int(h["factor_certeza"]),
                      h["especialista"], h["accion_recomendada"], int(h["validada"])) for h in kb["hipotesis"]]
        condiciones = [(c["hipotesis"], c["pregunta"], int(c["valor_respuesta"]), int(c["orden"]))
                       for c in kb["condiciones"]]
        with self._candado:
            janus.query_once("motor:cargar(P, H, C)", {"P": preguntas, "H": hipotesis, "C": condiciones})
            self.categorias = list(kb["categorias"])
            self.preguntas = {p["codigo"]: p for p in kb["preguntas"]}
            self.hipotesis = {h["codigo"]: h for h in kb["hipotesis"]}
            return janus.query_once("motor:total_reglas(N)")["N"]

    def recargar(self) -> int:
        """Vuelve a leer la base de MySQL; al iniciar y tras cada cambio del experto."""
        return self.cargar(self.repositorio.leer_base())

    @staticmethod
    def _hechos(evidencias) -> list[tuple[str, int]]:
        return [(e.pregunta, int(e.valor)) if hasattr(e, "pregunta") else (e[0], int(e[1])) for e in evidencias]

    def paso(self, categoria: str, evidencias) -> tuple[str, str | None]:
        """Un ciclo del motor de reglas: ('pregunta'|'diagnostico'|'ninguno', codigo)."""
        with self._candado:
            r = janus.query_once("motor:paso(C, R, T, X)", {"C": categoria, "R": self._hechos(evidencias)})
        return r["T"], r["X"] or None

    def estados(self, categoria: str, evidencias) -> dict[str, str]:
        """Estado logico de cada regla: descartada, confirmada o en_evaluacion."""
        with self._candado:
            r = janus.query_once("motor:estado_hipotesis(C, R, E)", {"C": categoria, "R": self._hechos(evidencias)})
        return {h: e for h, e in r["E"]}

    def confirma(self, categoria: str, evidencias, hipotesis: str) -> bool:
        """True si la regla se cumple logicamente: todos sus antecedentes respondidos y coincidentes."""
        return self.estados(categoria, evidencias).get(hipotesis) == "confirmada"

    def explicacion(self, hipotesis: str) -> list[tuple[str, int]]:
        with self._candado:
            r = janus.query_once("motor:explicacion(H, P)", {"H": hipotesis})
        return [(p, v) for p, v in r["P"]]

    def arbol(self, categoria: str, respuestas: tuple = ()) -> dict:
        """Arbol de decision de la categoria, simulando las dos respuestas a cada pregunta del motor."""
        tipo, codigo = self.paso(categoria, list(respuestas))
        if tipo != "pregunta":
            return {"tipo": tipo, "codigo": codigo}
        return {"tipo": "pregunta", "codigo": codigo,
                "si": self.arbol(categoria, respuestas + ((codigo, 1),)),
                "no": self.arbol(categoria, respuestas + ((codigo, 0),))}
