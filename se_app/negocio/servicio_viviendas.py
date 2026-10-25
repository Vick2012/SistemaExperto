"""Casos de uso CU02, CU06 y CU07: viviendas, tablero, historial y citas del consultante."""
from .errores import AccesoDenegado


class ServicioViviendas:
    def __init__(self, atenciones):
        # atenciones: RepositorioAtenciones (capa de datos).
        self.atenciones = atenciones

    def viviendas(self, id_usuario: int) -> list[dict]:
        return self.atenciones.viviendas(id_usuario)

    def crear_vivienda(self, id_usuario: int, alias: str, direccion: str, ciudad: str, tipo: str,
                       antiguedad: str) -> int:
        return self.atenciones.crear_vivienda(id_usuario, {
            "alias": alias.strip(), "direccion": direccion.strip(), "ciudad": ciudad.strip(), "tipo_vivienda": tipo,
            "antiguedad_anios": int(antiguedad) if str(antiguedad).isdigit() else None})

    def tablero(self, id_usuario: int) -> dict:
        return {"viviendas": self.atenciones.viviendas(id_usuario),
                "indicadores": self.atenciones.indicadores(id_usuario),
                "recientes": self.atenciones.historial(id_usuario, limite=5),
                "recurrentes": self.atenciones.recurrentes(id_usuario)}

    def historial(self, id_usuario: int, categoria: str = "", zona: str = "") -> list[dict]:
        return self.atenciones.historial(id_usuario, categoria, zona)

    def recurrentes(self, id_usuario: int) -> list[dict]:
        return self.atenciones.recurrentes(id_usuario)

    def citas(self, id_usuario: int, id_atencion: int | None = None) -> list[dict]:
        return self.atenciones.citas(id_usuario, id_atencion)

    def agendar(self, id_atencion: int, id_usuario: int, fecha: str, observaciones: str) -> int:
        try:
            return self.atenciones.crear_cita(id_atencion, id_usuario, fecha.replace("T", " "), observaciones.strip())
        except PermissionError as e:
            raise AccesoDenegado(str(e)) from e

    def cancelar_cita(self, id_cita: int, id_usuario: int) -> None:
        self.atenciones.cancelar_cita(id_cita, id_usuario)
