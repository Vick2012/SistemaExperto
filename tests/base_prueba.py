"""Base de conocimiento minima en memoria para las pruebas unitarias (sin MySQL).

RepositorioEnMemoria implementa la misma interfaz que RepositorioConocimiento,
de modo que los motores de la capa de negocio se prueban sin la capa de datos.
"""
from se_app.negocio.modelos import Antecedente, Hipotesis, Pregunta

REGLAS = {
    "E05": ("Critica", 93, [("olor_quemado", 1), ("sobrecalentamiento", 1)]),
    "E01": ("Alta", 88, [("olor_quemado", 1), ("sobrecalentamiento", 0), ("breaker", 1)]),
    "E08": ("Alta", 76, [("olor_quemado", 1), ("sobrecalentamiento", 0), ("breaker", 0)]),
    "E02": ("Critica", 92, [("olor_quemado", 0), ("chispas", 1)]),
}
PREGUNTAS = ("olor_quemado", "sobrecalentamiento", "breaker", "chispas")


def base_minima() -> dict:
    """Formato de RepositorioConocimiento.leer_base(), para cargar el motor Prolog."""
    return {
        "categorias": [{"codigo": "ELE", "nombre": "Eléctrica"}],
        "preguntas": [{"codigo": c, "categoria": "ELE", "texto_pregunta": c, "enunciado_positivo": c,
                       "enunciado_negativo": "no " + c} for c in PREGUNTAS],
        "hipotesis": [{"codigo": h, "categoria": "ELE", "diagnostico": h, "nivel_urgencia": u, "factor_certeza": fc,
                       "especialista": "x", "accion_recomendada": "y", "validada": 1} for h, (u, fc, _) in REGLAS.items()],
        "condiciones": [{"hipotesis": h, "pregunta": p, "valor_respuesta": v, "orden": i + 1}
                        for h, (_, _, conds) in REGLAS.items() for i, (p, v) in enumerate(conds)],
    }


class RepositorioEnMemoria:
    def __init__(self):
        self.consultas = 0          # cuantas consultas granulares hizo el motor

    def leer_base(self):
        return base_minima()

    def preguntas_de_categoria(self, categoria):
        return [Pregunta(c, "ELE", c, c, "no " + c) for c in PREGUNTAS]

    def hipotesis_activas(self, categoria):
        return [Hipotesis(h, "ELE", h, u, fc) for h, (u, fc, _) in REGLAS.items()]

    def antecedentes_de_pregunta(self, pregunta):
        self.consultas += 1
        return [Antecedente(h, p, v) for h, (_, _, conds) in REGLAS.items() for p, v in conds if p == pregunta]

    def antecedentes_de_hipotesis(self, hipotesis):
        return [Antecedente(hipotesis, p, v) for p, v in REGLAS[hipotesis][2]]
