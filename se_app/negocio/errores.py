"""Excepciones de la capa de negocio. La capa de presentacion las traduce a respuestas web."""


class ErrorNegocio(Exception):
    pass


class AccesoDenegado(ErrorNegocio):
    """El recurso no existe o no pertenece al usuario."""


class ErrorValidacion(ErrorNegocio):
    """Datos invalidos. 'errores' detalla los campos cuando aplica."""

    def __init__(self, mensaje: str = "", errores: dict | None = None):
        super().__init__(mensaje)
        self.errores = errores or {}


class ErrorAcceso(ErrorNegocio):
    """Credenciales invalidas o cuenta bloqueada (RF01)."""
