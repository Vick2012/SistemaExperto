"""Entidades del dominio del sistema experto."""
import math
from dataclasses import dataclass, field

# Codigo de la hipotesis H0: "no hay una falla identificable con las reglas".
H0 = "H0"
URGENCIAS = ("Critica", "Alta", "Media", "Baja")


@dataclass(frozen=True)
class Pregunta:
    """Sintoma formulado como pregunta Si/No."""
    codigo: str
    categoria: str
    texto: str
    enunciado_si: str
    enunciado_no: str

    def enunciado(self, valor: int) -> str:
        """Redaccion de la respuesta dada, para las explicaciones."""
        return self.enunciado_si if valor else self.enunciado_no


@dataclass(frozen=True)
class Hipotesis:
    """Consecuente (Then) de una regla, con sus metadatos."""
    codigo: str
    categoria: str
    diagnostico: str
    urgencia: str | None
    certeza: int                 # factor de certeza del experto, 0 a 100
    especialista: str | None = None
    accion: str | None = None
    validada: bool = True
    fuente: str | None = None
    id: int | None = None

    @property
    def es_h0(self) -> bool:
        return self.codigo == H0

    @staticmethod
    def sin_falla(categoria: str) -> "Hipotesis":
        return Hipotesis(H0, categoria, "Sin falla identificable con las reglas", None, 0)


@dataclass(frozen=True)
class Antecedente:
    """Fila de un granulo: la regla 'hipotesis' espera 'valor' en 'pregunta'."""
    hipotesis: str
    pregunta: str
    valor: int


@dataclass(frozen=True)
class Evidencia:
    """Respuesta del usuario: un hecho de la memoria de trabajo."""
    pregunta: str
    valor: int


@dataclass(frozen=True)
class HipotesisPonderada:
    hipotesis: Hipotesis
    previa: float                # P(H)
    probabilidad: float          # P(H | evidencias)

    @property
    def porcentaje(self) -> float:
        return round(self.probabilidad * 100, 1)


@dataclass
class Distribucion:
    """Distribucion de probabilidad sobre las hipotesis de una categoria."""
    probabilidades: dict[str, float]
    previas: dict[str, float]
    hipotesis: dict[str, Hipotesis]

    def normalizada(self, valores: dict[str, float]) -> "Distribucion":
        total = sum(valores.values()) or 1.0
        return Distribucion({h: v / total for h, v in valores.items()}, self.previas, self.hipotesis)

    def lider(self) -> Hipotesis:
        codigo = max(self.probabilidades, key=self.probabilidades.get)
        return self.hipotesis[codigo]

    def probabilidad(self, codigo: str) -> float:
        return self.probabilidades.get(codigo, 0.0)

    def entropia(self) -> float:
        """Incertidumbre en bits: 0 = una sola hipotesis posible."""
        return -sum(p * math.log2(p) for p in self.probabilidades.values() if p > 0)

    def ranking(self, n: int | None = None, incluir_h0: bool = True) -> list[HipotesisPonderada]:
        orden = sorted(self.probabilidades, key=lambda h: (-self.probabilidades[h], h))
        if not incluir_h0:
            orden = [h for h in orden if h != H0]
        return [HipotesisPonderada(self.hipotesis[h], self.previas[h], self.probabilidades[h]) for h in orden[:n]]


@dataclass
class Decision:
    """Resultado de un ciclo del motor: preguntar o concluir."""
    distribucion: Distribucion
    pregunta: Pregunta | None = None
    ganancia: float = 0.0                         # bits de informacion esperados de la pregunta
    antecedentes: list[Antecedente] = field(default_factory=list)   # granulo consultado de la pregunta

    @property
    def concluye(self) -> bool:
        return self.pregunta is None

    @property
    def conclusion(self) -> Hipotesis:
        return self.distribucion.lider()
