"""Punto de entrada: uvicorn se_app.main:app

La aplicacion esta organizada en tres capas:
    se_app/presentacion  controladores HTTP, vistas Jinja2 + HTMX
    se_app/negocio       motor bayesiano, motor de reglas Prolog y servicios
    se_app/datos         repositorios sobre MySQL
y se ensambla en se_app/contenedor.py.
"""
from .presentacion.app import app  # noqa: F401
