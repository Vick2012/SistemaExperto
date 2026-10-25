"""Acceso a la base de conocimiento (se_base_conocimiento)."""
from ..negocio.modelos import Antecedente, Hipotesis, Pregunta
from .conexion import BaseDatos

BC = "se_base_conocimiento"


class RepositorioConocimiento:
    # Campos de una regla que el experto puede editar desde el panel (CU08, CU09).
    CAMPOS_EDITABLES = ("diagnostico", "nivel_urgencia", "factor_certeza", "especialista",
                        "accion_recomendada", "validada", "activa")

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    # ------------------------------------------------------------ consultas granulares del motor

    def categorias(self) -> list[dict]:
        return self.bd.consultar(
            f"SELECT id_categoria, codigo, nombre, descripcion FROM {BC}.categoria WHERE activa = 1 ORDER BY orden")

    def preguntas_de_categoria(self, categoria: str) -> list[Pregunta]:
        filas = self.bd.consultar(
            f"SELECT p.codigo, c.codigo AS categoria, p.texto_pregunta, p.enunciado_positivo, p.enunciado_negativo "
            f"FROM {BC}.pregunta p JOIN {BC}.categoria c ON c.id_categoria = p.id_categoria "
            f"WHERE c.codigo = %s AND p.activa = 1 ORDER BY p.id_pregunta", (categoria,))
        return [Pregunta(f["codigo"], f["categoria"], f["texto_pregunta"], f["enunciado_positivo"],
                         f["enunciado_negativo"]) for f in filas]

    def hipotesis_activas(self, categoria: str) -> list[Hipotesis]:
        """Hipotesis candidatas de la categoria (consecuentes de las reglas activas)."""
        filas = self.bd.consultar(
            f"SELECT h.id_hipotesis, h.codigo, c.codigo AS categoria, h.diagnostico, h.nivel_urgencia, "
            f"       h.factor_certeza, h.especialista, h.accion_recomendada, h.validada, h.fuente "
            f"FROM {BC}.hipotesis h JOIN {BC}.categoria c ON c.id_categoria = h.id_categoria "
            f"WHERE c.codigo = %s AND h.activa = 1 ORDER BY h.codigo", (categoria,))
        return [self._a_hipotesis(f) for f in filas]

    def antecedentes_de_pregunta(self, pregunta: str) -> list[Antecedente]:
        """Consulta granular: que reglas activas usan la pregunta y que respuesta esperan.

        Es la consulta que el motor bayesiano repite tras cada respuesta y
        para cada pregunta candidata (ver 06_inferencia_bayesiana.sql).
        """
        filas = self.bd.consultar(
            f"SELECT h.codigo AS hipotesis, p.codigo AS pregunta, r.valor_respuesta "
            f"FROM {BC}.respuesta r "
            f"JOIN {BC}.hipotesis h ON h.id_hipotesis = r.id_hipotesis "
            f"JOIN {BC}.pregunta  p ON p.id_pregunta  = r.id_pregunta "
            f"WHERE p.codigo = %s AND h.activa = 1 ORDER BY h.codigo", (pregunta,))
        return [Antecedente(f["hipotesis"], f["pregunta"], int(f["valor_respuesta"])) for f in filas]

    def antecedentes_de_hipotesis(self, hipotesis: str) -> list[Antecedente]:
        """Granulo completo de una regla: sus antecedentes If/And en orden."""
        filas = self.bd.consultar(
            f"SELECT h.codigo AS hipotesis, p.codigo AS pregunta, r.valor_respuesta "
            f"FROM {BC}.respuesta r "
            f"JOIN {BC}.hipotesis h ON h.id_hipotesis = r.id_hipotesis "
            f"JOIN {BC}.pregunta  p ON p.id_pregunta  = r.id_pregunta "
            f"WHERE h.codigo = %s ORDER BY r.orden", (hipotesis,))
        return [Antecedente(f["hipotesis"], f["pregunta"], int(f["valor_respuesta"])) for f in filas]

    def hipotesis(self, codigo: str) -> Hipotesis | None:
        f = self.bd.consultar_uno(
            f"SELECT h.id_hipotesis, h.codigo, c.codigo AS categoria, h.diagnostico, h.nivel_urgencia, "
            f"       h.factor_certeza, h.especialista, h.accion_recomendada, h.validada, h.fuente "
            f"FROM {BC}.hipotesis h JOIN {BC}.categoria c ON c.id_categoria = h.id_categoria "
            f"WHERE h.codigo = %s", (codigo,))
        return self._a_hipotesis(f) if f else None

    @staticmethod
    def _a_hipotesis(f: dict) -> Hipotesis:
        return Hipotesis(f["codigo"], f["categoria"], f["diagnostico"], f["nivel_urgencia"], int(f["factor_certeza"]),
                         f["especialista"], f["accion_recomendada"], bool(f["validada"]), f["fuente"], f["id_hipotesis"])

    # ------------------------------------------------------------ base completa (motor de reglas en Prolog)

    def leer_base(self) -> dict:
        """Base de conocimiento activa, lista para cargar en el motor Prolog."""
        preguntas = self.bd.consultar(
            f"SELECT p.codigo, c.codigo AS categoria, p.texto_pregunta, p.enunciado_positivo, p.enunciado_negativo "
            f"FROM {BC}.pregunta p JOIN {BC}.categoria c ON c.id_categoria = p.id_categoria WHERE p.activa = 1")
        hipotesis = self.bd.consultar(
            f"SELECT h.codigo, c.codigo AS categoria, h.diagnostico, h.nivel_urgencia, h.factor_certeza, "
            f"       h.especialista, h.accion_recomendada, h.validada "
            f"FROM {BC}.hipotesis h JOIN {BC}.categoria c ON c.id_categoria = h.id_categoria WHERE h.activa = 1")
        condiciones = self.bd.consultar(
            f"SELECT h.codigo AS hipotesis, p.codigo AS pregunta, r.valor_respuesta, r.orden "
            f"FROM {BC}.respuesta r JOIN {BC}.hipotesis h ON h.id_hipotesis = r.id_hipotesis "
            f"JOIN {BC}.pregunta p ON p.id_pregunta = r.id_pregunta WHERE h.activa = 1")
        return {"categorias": self.categorias(), "preguntas": preguntas, "hipotesis": hipotesis,
                "condiciones": condiciones}

    # ------------------------------------------------------------ panel del experto (CU08, CU09)

    def resumen(self) -> dict:
        return self.bd.consultar_uno(
            f"SELECT (SELECT COUNT(*) FROM {BC}.pregunta  WHERE activa = 1) AS preguntas, "
            f"       (SELECT COUNT(*) FROM {BC}.hipotesis WHERE activa = 1) AS hipotesis, "
            f"       (SELECT COUNT(*) FROM {BC}.hipotesis WHERE activa = 1 AND validada = 0) AS pendientes, "
            f"       (SELECT COUNT(*) FROM {BC}.hipotesis WHERE activa = 1 AND nivel_urgencia = 'Critica') AS criticas") or {}

    def reglas_de_categoria(self, categoria: str) -> list[dict]:
        """Todas las reglas de la categoria, activas o no, con su numero de condiciones."""
        return self.bd.consultar(
            f"SELECT h.id_hipotesis, h.codigo, h.diagnostico, h.nivel_urgencia, h.factor_certeza, "
            f"       h.especialista, h.accion_recomendada, h.fuente, h.validada, h.activa, "
            f"       COUNT(r.id_respuesta) AS condiciones "
            f"FROM {BC}.hipotesis h JOIN {BC}.categoria c ON c.id_categoria = h.id_categoria "
            f"LEFT JOIN {BC}.respuesta r ON r.id_hipotesis = h.id_hipotesis "
            f"WHERE c.codigo = %s GROUP BY h.id_hipotesis ORDER BY h.codigo", (categoria,))

    def regla(self, codigo: str) -> dict | None:
        return self.bd.consultar_uno(
            f"SELECT h.*, c.codigo AS categoria, c.nombre AS categoria_nombre "
            f"FROM {BC}.hipotesis h JOIN {BC}.categoria c ON c.id_categoria = h.id_categoria "
            f"WHERE h.codigo = %s", (codigo,))

    def granulo(self, codigo: str) -> list[dict]:
        """Condiciones If/And de una regla con sus textos, para mostrarlas."""
        return self.bd.consultar(
            f"SELECT r.orden, r.valor_respuesta, p.codigo, p.texto_pregunta, "
            f"       IF(r.valor_respuesta = 1, p.enunciado_positivo, p.enunciado_negativo) AS enunciado "
            f"FROM {BC}.respuesta r JOIN {BC}.hipotesis h ON h.id_hipotesis = r.id_hipotesis "
            f"JOIN {BC}.pregunta p ON p.id_pregunta = r.id_pregunta WHERE h.codigo = %s ORDER BY r.orden", (codigo,))

    def actualizar_regla(self, codigo: str, cambios: dict, id_usuario: int) -> list[str]:
        """Aplica los cambios y registra cada uno en la bitacora (RF07, RNF04). Devuelve los campos cambiados."""
        actual = self.regla(codigo)
        if actual is None:
            raise ValueError(f"No existe la hipotesis {codigo}")
        distintos = {k: v for k, v in cambios.items()
                     if k in self.CAMPOS_EDITABLES and str(actual[k]) != str(v)}
        if not distintos:
            return []
        with self.bd.transaccion() as cnx:
            cur = cnx.cursor()
            asignaciones = ", ".join(f"{k} = %s" for k in distintos)
            cur.execute(f"UPDATE {BC}.hipotesis SET {asignaciones} WHERE codigo = %s", (*distintos.values(), codigo))
            for campo, nuevo in distintos.items():
                accion = ("ACTIVAR" if int(nuevo) else "DESACTIVAR") if campo == "activa" else "MODIFICAR"
                cur.execute(
                    "INSERT INTO bitacora_conocimiento (id_usuario, tabla_afectada, codigo_registro, accion, detalle) "
                    "VALUES (%s, 'hipotesis', %s, %s, %s)",
                    (id_usuario, codigo, accion, f"{campo}: {actual[campo]} -> {nuevo}"[:500]))
        return list(distintos)

    def bitacora(self, limite: int = 200) -> list[dict]:
        return self.bd.consultar(
            "SELECT b.*, u.usuario, u.nombres, u.apellidos FROM bitacora_conocimiento b "
            "JOIN usuario u ON u.id_usuario = b.id_usuario ORDER BY b.fecha_cambio DESC LIMIT %s", (limite,))
