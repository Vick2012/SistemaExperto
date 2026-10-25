"""Casos de uso CU08, CU09 y CU11: mantener la base de conocimiento y revisar su coherencia."""
from .errores import ErrorValidacion
from .modelos import URGENCIAS
from .motor_prolog import MotorProlog


class ServicioConocimiento:
    def __init__(self, conocimiento, reglas: MotorProlog):
        # conocimiento: RepositorioConocimiento (capa de datos).
        self.conocimiento = conocimiento
        self.reglas = reglas

    def resumen(self) -> dict:
        return self.conocimiento.resumen()

    def reglas_de_categoria(self, categoria: str, solo_pendientes: bool = False) -> list[dict]:
        filas = self.conocimiento.reglas_de_categoria(categoria)
        return [f for f in filas if not f["validada"]] if solo_pendientes else filas

    def granulo(self, codigo: str, usuario: dict) -> dict:
        """Regla, sus condiciones If/And y si el usuario puede desactivarla (RF03)."""
        h = self.conocimiento.regla(codigo) if codigo else None
        return {"h": h, "condiciones": self.conocimiento.granulo(codigo) if h else [],
                "puede_desactivar": bool(h) and (h["nivel_urgencia"] != "Critica" or usuario["rol"] == "ADMINISTRADOR")}

    def guardar_regla(self, codigo: str, cambios: dict, usuario: dict) -> list[str]:
        """Valida y guarda los cambios de una regla; el motor de reglas razona desde ya con ella."""
        actual = self.conocimiento.regla(codigo)
        if not 0 <= int(cambios["factor_certeza"]) <= 100:
            raise ErrorValidacion("El factor de certeza debe estar entre 0 y 100.")
        if cambios["nivel_urgencia"] not in URGENCIAS:
            raise ErrorValidacion("Nivel de urgencia no válido.")
        if (actual and not int(cambios["activa"]) and actual["activa"] and actual["nivel_urgencia"] == "Critica"
                and usuario["rol"] != "ADMINISTRADOR"):
            raise ErrorValidacion("Solo un administrador puede desactivar reglas de urgencia crítica (RF03).")
        guardados = self.conocimiento.actualizar_regla(codigo, cambios, usuario["id"])
        if guardados:
            self.reglas.recargar()
        return guardados

    def recargar(self) -> int:
        return self.reglas.recargar()

    def ultimos_cambios(self, limite: int = 5) -> list[dict]:
        return self.conocimiento.bitacora(limite)

    def bitacora(self) -> list[dict]:
        return self.conocimiento.bitacora()

    def arbol(self, categoria: str) -> dict:
        """Arbol de decision generado por el motor de reglas y chequeo de coherencia (RF05)."""
        if not self.reglas.categoria(categoria):
            categoria = self.reglas.categorias[0]["codigo"]
        raiz = self.reglas.arbol(categoria)
        hojas, profundidad = self._medir(raiz)
        reglas = {c for c, h in self.reglas.hipotesis.items() if h["categoria"] == categoria}
        alcanzadas = [h for h in hojas if h]
        return {"raiz": raiz, "categoria": categoria, "categoria_nombre": self.reglas.categoria(categoria)["nombre"],
                "preguntas": self.reglas.preguntas, "hipotesis": self.reglas.hipotesis,
                "total_hojas": len(hojas), "profundidad": profundidad, "reglas": len(reglas),
                "inalcanzables": sorted(reglas - set(alcanzadas)),
                "repetidas": len(alcanzadas) - len(set(alcanzadas))}

    def _medir(self, nodo: dict, nivel: int = 1) -> tuple[list, int]:
        """Hojas del arbol (codigos; None = conclusion por defecto) y profundidad maxima."""
        if nodo["tipo"] != "pregunta":
            return [nodo["codigo"]], nivel
        hs, ps = self._medir(nodo["si"], nivel + 1)
        hn, pn = self._medir(nodo["no"], nivel + 1)
        return hs + hn, max(ps, pn)
