"""Acceso a la operacion diaria (se_transaccional): viviendas, atenciones,
respuestas, diagnosticos, ranking de hipotesis, citas e historial.

Toda consulta de un consultante filtra por su id_usuario a traves de la
vivienda, para que solo vea lo suyo (RF06).
"""
from ..negocio.modelos import Evidencia, Hipotesis, HipotesisPonderada
from .conexion import BaseDatos

BC = "se_base_conocimiento"


class RepositorioAtenciones:
    def __init__(self, bd: BaseDatos):
        self.bd = bd

    # ------------------------------------------------------------ viviendas (CU02)

    def viviendas(self, id_usuario: int) -> list[dict]:
        return self.bd.consultar(
            "SELECT v.*, COUNT(a.id_atencion) AS atenciones, MAX(a.fecha_inicio) AS ultima "
            "FROM vivienda v LEFT JOIN atencion a ON a.id_vivienda = v.id_vivienda "
            "WHERE v.id_usuario = %s AND v.activa = 1 GROUP BY v.id_vivienda ORDER BY v.id_vivienda", (id_usuario,))

    def crear_vivienda(self, id_usuario: int, datos: dict) -> int:
        return self.bd.ejecutar(
            "INSERT INTO vivienda (id_usuario, alias, direccion, ciudad, tipo_vivienda, antiguedad_anios) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (id_usuario, datos["alias"], datos["direccion"], datos["ciudad"], datos["tipo_vivienda"],
             datos.get("antiguedad_anios") or None))

    def vivienda_es_de(self, id_vivienda: int, id_usuario: int) -> bool:
        return bool(self.bd.consultar_uno("SELECT 1 AS ok FROM vivienda WHERE id_vivienda = %s AND id_usuario = %s",
                                          (id_vivienda, id_usuario)))

    # ------------------------------------------------------------ atenciones y memoria de trabajo (CU03)

    def crear_atencion(self, id_vivienda: int, categoria: str, zona: str) -> int:
        return self.bd.ejecutar(
            f"INSERT INTO atencion (id_vivienda, id_categoria, zona_vivienda) "
            f"SELECT %s, id_categoria, %s FROM {BC}.categoria WHERE codigo = %s", (id_vivienda, zona, categoria))

    def atencion(self, id_atencion: int, id_usuario: int) -> dict | None:
        """La atencion, solo si pertenece al usuario."""
        return self.bd.consultar_uno(
            f"SELECT a.*, c.codigo AS categoria, c.nombre AS categoria_nombre, v.alias AS vivienda, v.direccion, v.ciudad "
            f"FROM atencion a JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
            f"JOIN {BC}.categoria c ON c.id_categoria = a.id_categoria "
            f"WHERE a.id_atencion = %s AND v.id_usuario = %s", (id_atencion, id_usuario))

    def evidencias(self, id_atencion: int) -> list[Evidencia]:
        """Memoria de trabajo de la atencion, en el orden en que se respondio."""
        filas = self.bd.consultar(
            f"SELECT p.codigo, ar.respuesta FROM atencion_respuesta ar "
            f"JOIN {BC}.pregunta p ON p.id_pregunta = ar.id_pregunta WHERE ar.id_atencion = %s ORDER BY ar.orden",
            (id_atencion,))
        return [Evidencia(f["codigo"], int(f["respuesta"])) for f in filas]

    def registrar_respuesta(self, id_atencion: int, pregunta: str, valor: int) -> None:
        self.bd.ejecutar(
            f"INSERT INTO atencion_respuesta (id_atencion, id_pregunta, respuesta, orden) "
            f"SELECT %s, p.id_pregunta, %s, "
            f"       (SELECT COALESCE(MAX(orden), 0) + 1 FROM atencion_respuesta WHERE id_atencion = %s) "
            f"FROM {BC}.pregunta p WHERE p.codigo = %s", (id_atencion, valor, id_atencion, pregunta))

    def deshacer_respuesta(self, id_atencion: int) -> None:
        self.bd.ejecutar("DELETE FROM atencion_respuesta WHERE id_atencion = %s ORDER BY orden DESC LIMIT 1",
                         (id_atencion,))

    def borrar_respuestas(self, id_atencion: int) -> None:
        self.bd.ejecutar("DELETE FROM atencion_respuesta WHERE id_atencion = %s", (id_atencion,))

    def cerrar(self, id_atencion: int, conclusion: Hipotesis | None, ranking: list[HipotesisPonderada]) -> None:
        """Guarda el diagnostico y el ranking de hipotesis como copia historica (RNF20) y cierra la atencion.

        conclusion = None registra la conclusion por defecto (RNF22).
        """
        with self.bd.transaccion() as cnx:
            cur = cnx.cursor()
            cur.execute("DELETE FROM atencion_diagnostico WHERE id_atencion = %s", (id_atencion,))
            cur.execute("DELETE FROM atencion_hipotesis WHERE id_atencion = %s", (id_atencion,))
            if conclusion:
                cur.execute(
                    "INSERT INTO atencion_diagnostico (id_atencion, id_hipotesis, diagnostico_texto, nivel_urgencia, "
                    "  especialista_sugerido, accion_recomendada, factor_certeza) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (id_atencion, conclusion.id, conclusion.diagnostico, conclusion.urgencia,
                     conclusion.especialista, conclusion.accion, conclusion.certeza))
                estado = "DIAGNOSTICADA"
            else:
                cur.execute("INSERT INTO atencion_diagnostico (id_atencion, id_hipotesis, diagnostico_texto) "
                            "VALUES (%s, NULL, 'Sin diagnóstico concluyente')", (id_atencion,))
                estado = "SIN_DIAGNOSTICO"
            for posicion, hp in enumerate(ranking, 1):
                cur.execute(
                    "INSERT INTO atencion_hipotesis (id_atencion, id_hipotesis, codigo_hipotesis, diagnostico_texto, "
                    "  posicion, probabilidad_previa, probabilidad) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (id_atencion, hp.hipotesis.id, hp.hipotesis.codigo, hp.hipotesis.diagnostico, posicion,
                     round(hp.previa, 6), round(hp.probabilidad, 6)))
            cur.execute("UPDATE atencion SET estado = %s, fecha_fin = NOW() WHERE id_atencion = %s",
                        (estado, id_atencion))

    def reabrir(self, id_atencion: int) -> None:
        """Permite corregir respuestas de una atencion ya cerrada."""
        with self.bd.transaccion() as cnx:
            cur = cnx.cursor()
            cur.execute("DELETE FROM atencion_diagnostico WHERE id_atencion = %s", (id_atencion,))
            cur.execute("DELETE FROM atencion_hipotesis WHERE id_atencion = %s", (id_atencion,))
            cur.execute("UPDATE atencion SET estado = 'EN_CURSO', fecha_fin = NULL WHERE id_atencion = %s",
                        (id_atencion,))

    def diagnostico(self, id_atencion: int) -> dict | None:
        return self.bd.consultar_uno(
            f"SELECT d.*, h.codigo AS codigo_hipotesis, h.validada, h.fuente "
            f"FROM atencion_diagnostico d LEFT JOIN {BC}.hipotesis h ON h.id_hipotesis = d.id_hipotesis "
            f"WHERE d.id_atencion = %s", (id_atencion,))

    def ranking(self, id_atencion: int) -> list[dict]:
        """Hipotesis ponderadas guardadas al cerrar la atencion, de la mas probable a la menos."""
        return self.bd.consultar(
            f"SELECT ah.*, h.nivel_urgencia FROM atencion_hipotesis ah "
            f"LEFT JOIN {BC}.hipotesis h ON h.id_hipotesis = ah.id_hipotesis "
            f"WHERE ah.id_atencion = %s ORDER BY ah.posicion", (id_atencion,))

    # ------------------------------------------------------------ citas (CU06)

    def crear_cita(self, id_atencion: int, id_usuario: int, fecha: str, observaciones: str | None) -> int:
        d = self.bd.consultar_uno(
            "SELECT d.id_diagnostico, d.especialista_sugerido FROM atencion_diagnostico d "
            "JOIN atencion a ON a.id_atencion = d.id_atencion JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
            "WHERE d.id_atencion = %s AND v.id_usuario = %s AND d.id_hipotesis IS NOT NULL", (id_atencion, id_usuario))
        if not d:
            raise PermissionError("Solo se agenda a partir de un diagnóstico concluyente propio.")
        return self.bd.ejecutar(
            "INSERT INTO cita (id_diagnostico, tipo_especialista, fecha_programada, observaciones) VALUES (%s, %s, %s, %s)",
            (d["id_diagnostico"], d["especialista_sugerido"], fecha, observaciones or None))

    def citas(self, id_usuario: int, id_atencion: int | None = None) -> list[dict]:
        filtro, params = ("", (id_usuario,)) if not id_atencion else (" AND a.id_atencion = %s", (id_usuario, id_atencion))
        return self.bd.consultar(
            "SELECT ci.*, d.diagnostico_texto, d.nivel_urgencia, a.id_atencion, a.zona_vivienda, v.alias AS vivienda "
            "FROM cita ci JOIN atencion_diagnostico d ON d.id_diagnostico = ci.id_diagnostico "
            "JOIN atencion a ON a.id_atencion = d.id_atencion JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
            "WHERE v.id_usuario = %s" + filtro + " ORDER BY ci.fecha_programada", params)

    def cancelar_cita(self, id_cita: int, id_usuario: int) -> None:
        self.bd.ejecutar(
            "UPDATE cita ci JOIN atencion_diagnostico d ON d.id_diagnostico = ci.id_diagnostico "
            "JOIN atencion a ON a.id_atencion = d.id_atencion JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
            "SET ci.estado = 'CANCELADA' WHERE ci.id_cita = %s AND v.id_usuario = %s", (id_cita, id_usuario))

    # ------------------------------------------------------------ historial e indicadores (CU07)

    def historial(self, id_usuario: int, categoria: str = "", zona: str = "", limite: int = 200) -> list[dict]:
        sql = (f"SELECT a.id_atencion, a.fecha_inicio, a.zona_vivienda, a.estado, c.codigo AS categoria, "
               f"       c.nombre AS categoria_nombre, v.alias AS vivienda, d.diagnostico_texto, d.nivel_urgencia, "
               f"       d.factor_certeza, ah.probabilidad "
               f"FROM atencion a JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
               f"JOIN {BC}.categoria c ON c.id_categoria = a.id_categoria "
               f"LEFT JOIN atencion_diagnostico d ON d.id_atencion = a.id_atencion "
               f"LEFT JOIN atencion_hipotesis ah ON ah.id_atencion = a.id_atencion AND ah.posicion = 1 "
               f"WHERE v.id_usuario = %s AND a.estado IN ('DIAGNOSTICADA', 'SIN_DIAGNOSTICO')")
        params = [id_usuario]
        if categoria:
            sql += " AND c.codigo = %s"
            params.append(categoria)
        if zona:
            sql += " AND a.zona_vivienda = %s"
            params.append(zona)
        sql += " ORDER BY a.fecha_inicio DESC LIMIT %s"
        params.append(limite)
        return self.bd.consultar(sql, tuple(params))

    def recurrentes(self, id_usuario: int) -> list[dict]:
        """Categorias que se repiten en una misma vivienda en los ultimos 90 dias (RF03)."""
        return self.bd.consultar(
            f"SELECT v.alias AS vivienda, c.nombre AS categoria, COUNT(*) AS veces "
            f"FROM atencion a JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
            f"JOIN {BC}.categoria c ON c.id_categoria = a.id_categoria "
            f"WHERE v.id_usuario = %s AND a.estado = 'DIAGNOSTICADA' AND a.fecha_inicio >= NOW() - INTERVAL 90 DAY "
            f"GROUP BY v.id_vivienda, c.id_categoria HAVING COUNT(*) >= 2", (id_usuario,))

    def indicadores(self, id_usuario: int) -> dict:
        return self.bd.consultar_uno(
            "SELECT "
            " (SELECT COUNT(*) FROM atencion a JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
            "   WHERE v.id_usuario = %s AND a.estado <> 'EN_CURSO' AND a.fecha_inicio >= DATE_FORMAT(NOW(), '%%Y-%%m-01')) AS mes, "
            " (SELECT COUNT(*) FROM atencion_diagnostico d JOIN atencion a ON a.id_atencion = d.id_atencion "
            "   JOIN vivienda v ON v.id_vivienda = a.id_vivienda WHERE v.id_usuario = %s AND d.nivel_urgencia = 'Critica') AS criticas, "
            " (SELECT COUNT(*) FROM cita ci JOIN atencion_diagnostico d ON d.id_diagnostico = ci.id_diagnostico "
            "   JOIN atencion a ON a.id_atencion = d.id_atencion JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
            "   WHERE v.id_usuario = %s AND ci.estado IN ('PROGRAMADA', 'CONFIRMADA') AND ci.fecha_programada >= NOW()) AS citas, "
            " (SELECT AVG(TIMESTAMPDIFF(SECOND, a.fecha_inicio, a.fecha_fin)) FROM atencion a "
            "   JOIN vivienda v ON v.id_vivienda = a.id_vivienda WHERE v.id_usuario = %s AND a.fecha_fin IS NOT NULL) AS segundos",
            (id_usuario, id_usuario, id_usuario, id_usuario)) or {}
