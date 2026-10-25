"""Motor de inferencia probabilistico (Bayes) con consultas granulares.

No es un sistema de condicionales: ninguna regla esta escrita en el codigo.
El conocimiento se lee de la base de conocimiento por granulos, en
consultas sucesivas, y todas las hipotesis de la categoria se ponderan a
la vez con el teorema de Bayes.

Modelo
------
Hipotesis: las reglas activas de la categoria, mas H0 ("sin falla
identificable"), que se comporta como una regla con el granulo vacio.

Probabilidad previa (antes de responder):
    P(H0) = PREVIA_H0
    P(H)  = (1 - PREVIA_H0) * FC(H) / suma de FC de la categoria

Verosimilitud de una respuesta e (pregunta q, valor v) dada H:
    q en el granulo de H y v es lo que H espera  ->  1 - ERROR_RESPUESTA
    q en el granulo de H y v no lo es            ->  ERROR_RESPUESTA
    q fuera del granulo de H (o H = H0):
        v = Si  ->  SINTOMA_AJENO        (un sintoma ajeno rara vez esta)
        v = No  ->  1 - SINTOMA_AJENO

Actualizacion tras cada respuesta (Bayes):
    P(H | e1..en) = P(e_n | H) * P(H | e1..en-1) / suma sobre todas las H

Seleccion de la pregunta: la de mayor ganancia de informacion esperada,
es decir, la que mas reduce la entropia de la distribucion. Si ninguna
aporta al menos GANANCIA_MINIMA, se verifican los antecedentes pendientes
de las hipotesis mas probables (como en el encadenamiento hacia atras).

Parada: la hipotesis lider supera UMBRAL_CONFIRMACION y todos sus
antecedentes estan respondidos, o ya no queda nada util por preguntar.
"""
from .modelos import H0, Antecedente, Decision, Distribucion, Evidencia, Hipotesis, Pregunta


class MotorBayesiano:
    ERROR_RESPUESTA = 0.02       # probabilidad de responder distinto de lo que la falla produce
    SINTOMA_AJENO = 0.10         # probabilidad de que este presente un sintoma que no es de la falla
    PREVIA_H0 = 0.05             # probabilidad previa de que no haya falla identificable
    UMBRAL_CONFIRMACION = 0.90   # probabilidad con la que se confirma la hipotesis lider
    GANANCIA_MINIMA = 0.02       # bits por debajo de los cuales una pregunta no se considera util
    RELEVANCIA_MINIMA = 0.01     # probabilidad por debajo de la cual una hipotesis ya no se verifica

    def __init__(self, repositorio):
        # repositorio: RepositorioConocimiento (capa de datos), inyectado.
        self.repositorio = repositorio

    # ------------------------------------------------------------ distribucion de probabilidad

    def distribucion_inicial(self, categoria: str) -> Distribucion:
        """Probabilidades previas, a partir del factor de certeza de cada regla."""
        reglas = self.repositorio.hipotesis_activas(categoria)                 # consulta granular 1
        hipotesis = {h.codigo: h for h in reglas}
        hipotesis[H0] = Hipotesis.sin_falla(categoria)
        suma_fc = sum(h.certeza for h in reglas) or 1
        previas = {h.codigo: (1 - self.PREVIA_H0) * h.certeza / suma_fc for h in reglas}
        previas[H0] = self.PREVIA_H0 if reglas else 1.0
        return Distribucion(dict(previas), previas, hipotesis)

    def verosimilitud(self, esperado: int | None, valor: int) -> float:
        """P(respuesta | H). 'esperado' es lo que el granulo de H espera, o None si H no usa la pregunta."""
        if esperado is None:
            return self.SINTOMA_AJENO if valor else 1 - self.SINTOMA_AJENO
        return 1 - self.ERROR_RESPUESTA if valor == esperado else self.ERROR_RESPUESTA

    def actualizar(self, distribucion: Distribucion, evidencia: Evidencia,
                   antecedentes: list[Antecedente] | None = None) -> Distribucion:
        """Aplica Bayes con una respuesta. Consulta el granulo de la pregunta en la base de conocimiento."""
        if antecedentes is None:
            antecedentes = self.repositorio.antecedentes_de_pregunta(evidencia.pregunta)   # consulta granular
        espera = {a.hipotesis: a.valor for a in antecedentes}
        conjunta = {h: p * self.verosimilitud(espera.get(h), evidencia.valor)
                    for h, p in distribucion.probabilidades.items()}
        return distribucion.normalizada(conjunta)

    def inferir(self, categoria: str, evidencias: list[Evidencia]) -> Distribucion:
        """Distribucion a posteriori tras todas las respuestas, aplicadas una a una."""
        return self.traza(categoria, evidencias)[-1]

    def traza(self, categoria: str, evidencias: list[Evidencia]) -> list[Distribucion]:
        """Distribucion inicial y la que queda despues de cada respuesta (para explicar el razonamiento)."""
        pasos = [self.distribucion_inicial(categoria)]
        for e in evidencias:
            pasos.append(self.actualizar(pasos[-1], e))
        return pasos

    # ------------------------------------------------------------ seleccion de la siguiente pregunta

    def ganancia(self, distribucion: Distribucion, antecedentes: list[Antecedente]) -> float:
        """Ganancia de informacion esperada (bits) de preguntar la pregunta de esos antecedentes."""
        espera = {a.hipotesis: a.valor for a in antecedentes}
        p_si = sum(p * self.verosimilitud(espera.get(h), 1) for h, p in distribucion.probabilidades.items())
        resultado = 0.0
        for valor, p_valor in ((1, p_si), (0, 1 - p_si)):
            if p_valor <= 0:
                continue
            conjunta = {h: p * self.verosimilitud(espera.get(h), valor) for h, p in distribucion.probabilidades.items()}
            resultado += p_valor * distribucion.normalizada(conjunta).entropia()
        return distribucion.entropia() - resultado

    def decidir(self, categoria: str, evidencias: list[Evidencia]) -> Decision:
        """Un ciclo del motor: siguiente pregunta o conclusion, con la distribucion actual."""
        distribucion = self.inferir(categoria, evidencias)
        respondidas = {e.pregunta for e in evidencias}
        candidatas = [p for p in self.repositorio.preguntas_de_categoria(categoria) if p.codigo not in respondidas]
        lider = distribucion.lider()
        pendientes_lider = self._pendientes(lider, respondidas)

        if not candidatas or (distribucion.probabilidad(lider.codigo) >= self.UMBRAL_CONFIRMACION
                              and not pendientes_lider):
            return Decision(distribucion)

        # Consultas granulares sucesivas: el granulo de cada pregunta candidata.
        granulos = {p.codigo: self.repositorio.antecedentes_de_pregunta(p.codigo) for p in candidatas}
        ganancias = {p.codigo: self.ganancia(distribucion, granulos[p.codigo]) for p in candidatas}
        mejor = max(candidatas, key=lambda p: ganancias[p.codigo])
        if ganancias[mejor.codigo] >= self.GANANCIA_MINIMA:
            return Decision(distribucion, mejor, ganancias[mejor.codigo], granulos[mejor.codigo])

        # Ninguna pregunta informa lo suficiente: verificar antecedentes de las mas probables.
        por_codigo = {p.codigo: p for p in candidatas}
        for hp in distribucion.ranking():
            if hp.probabilidad < self.RELEVANCIA_MINIMA:
                break
            for codigo in self._pendientes(hp.hipotesis, respondidas):
                if codigo in por_codigo:
                    return Decision(distribucion, por_codigo[codigo], ganancias[codigo], granulos[codigo])
        return Decision(distribucion)

    def _pendientes(self, hipotesis: Hipotesis, respondidas: set[str]) -> list[str]:
        """Antecedentes de la hipotesis que el usuario aun no ha respondido (consulta su granulo)."""
        if hipotesis.es_h0:
            return []
        return [a.pregunta for a in self.repositorio.antecedentes_de_hipotesis(hipotesis.codigo)
                if a.pregunta not in respondidas]

    # ------------------------------------------------------------ explicacion

    def aportes(self, evidencias: list[Evidencia], trayectoria: list[Distribucion], hipotesis: str) -> list[dict]:
        """Efecto de cada respuesta sobre una hipotesis: verosimilitud y probabilidad antes y despues."""
        filas = []
        for i, e in enumerate(evidencias):
            espera = {a.hipotesis: a.valor for a in self.repositorio.antecedentes_de_pregunta(e.pregunta)}
            esperado = espera.get(hipotesis)
            efecto = "neutral" if esperado is None else ("a favor" if esperado == e.valor else "en contra")
            filas.append({"pregunta": e.pregunta, "valor": e.valor, "espera": esperado, "efecto": efecto,
                          "verosimilitud": self.verosimilitud(esperado, e.valor),
                          "antes": trayectoria[i].probabilidad(hipotesis),
                          "despues": trayectoria[i + 1].probabilidad(hipotesis)})
        return filas
