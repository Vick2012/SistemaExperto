"""Acceso a MySQL.

Una sola conexion por peticion, tomada de un pool. Las consultas usan
nombres calificados (se_base_conocimiento.tabla / se_transaccional.tabla)
porque la aplicacion trabaja con los dos esquemas a la vez.
"""
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

from . import config

_pool = None


def _obtener_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="se_pool",
            pool_size=8,
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.ESQUEMA_TRANSACCIONAL,
            charset="utf8mb4",
            collation="utf8mb4_0900_ai_ci",
            autocommit=False,
            connection_timeout=5,
        )
    return _pool


@contextmanager
def conexion():
    """Entrega una conexion; confirma al salir o deshace si hubo error."""
    cnx = _obtener_pool().get_connection()
    try:
        yield cnx
        cnx.commit()
    except Exception:
        cnx.rollback()
        raise
    finally:
        cnx.close()


def consultar(sql: str, params: tuple = ()) -> list[dict]:
    with conexion() as cnx:
        cur = cnx.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur.fetchall()


def consultar_uno(sql: str, params: tuple = ()) -> dict | None:
    filas = consultar(sql, params)
    return filas[0] if filas else None


def ejecutar(sql: str, params: tuple = ()) -> int:
    """Ejecuta una escritura y devuelve el ultimo id insertado."""
    with conexion() as cnx:
        cur = cnx.cursor()
        cur.execute(sql, params)
        return cur.lastrowid


def disponible() -> bool:
    try:
        consultar("SELECT 1 AS ok")
        return True
    except mysql.connector.Error:
        return False
