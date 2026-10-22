# Sistema experto de diagnóstico de vivienda · Aplicación web

Capa de presentación y motor de inferencia del proyecto de Sistemas Expertos
(UMB, 2026). Sigue la arquitectura del manual:

```
Navegador ──HTMX──▶ FastAPI (se_app/main.py)
                       │
                       ├─▶ Motor de inferencia  SWI-Prolog  (prolog/motor.pl, vía Janus)
                       │
                       └─▶ MySQL 8: se_base_conocimiento  +  se_transaccional
```

- **La base de conocimiento no está en el código** (RNF19). Al arrancar, y cada vez que el experto
  cambia una regla, la aplicación lee las preguntas, hipótesis y respuestas de MySQL y las carga
  en Prolog como hechos `pregunta/5`, `hipotesis/8` y `condicion/4`.
- **El motor razona en Prolog**: encadenamiento hacia atrás (solo pregunta lo necesario),
  resolución de conflictos por severidad y factor de certeza, y conclusión por defecto (RNF22).
  Reproduce las consultas B3 y B5 de `04_consultas_granulos.sql`.
- **Diseño B · Centro de diagnóstico** (ver `../.21st/design.json`). El consultante ve un flujo sencillo;
  el experto y el administrador ven además el razonamiento del motor en vivo.

## Requisitos

| Herramienta | Versión probada |
|---|---|
| Python | 3.13 |
| SWI-Prolog | 10.0.2 (en `C:\Program Files\swipl`) |
| MySQL | 8.4 en Docker (contenedor `se-mysql`) |
| Node.js | solo para recompilar los estilos |

## Puesta en marcha

Todos los comandos se ejecutan desde la carpeta `aplicacion`.

1. **Encender MySQL.** Abra Docker Desktop y verifique que el contenedor `se-mysql` esté en verde.
   Si las bases no existen, ejecute en orden los scripts `01` a `04` de la carpeta del proyecto.

2. **Crear el entorno de Python** (solo la primera vez):

   ```bash
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```

3. **Configurar la conexión** (opcional). Se usa `../mysql_local_prueba.env`. Para cambiar algo,
   copie `.env.example` como `.env` y llene solo lo que quiera cambiar; los valores vacíos se ignoran.

4. **Crear los usuarios de prueba** (`admin`, `experto`, `consulta`) con contraseña cifrada.
   La contraseña de prueba es el valor `SEED_PASSWORD` de `.env.example`.

   ```bash
   .venv\Scripts\python -m scripts.semilla
   ```

5. **Iniciar la aplicación:**

   ```bash
   .venv\Scripts\python -m uvicorn se_app.main:app --reload --port 8000
   ```

   Abra http://127.0.0.1:8000 e inicie sesión.

## Pruebas

```bash
.venv\Scripts\python -m pytest -q tests
```

Las pruebas unitarias del motor no necesitan MySQL. Con MySQL encendido, además recorren la ruta
de **cada una de las reglas** de la base y los casos de la Tabla 52 del manual.

## Estilos

Tailwind se compila a un archivo local (la red no siempre alcanza el CDN):

```bash
npx tailwindcss@3.4.16 -i estilos/app.css -o se_app/static/css/app.css --minify
```

Recompile después de agregar clases nuevas en las plantillas. HTMX 2.0.4 está en
`se_app/static/js/htmx.min.js`.

## Estructura

```
aplicacion/
├── prolog/motor.pl          Motor de inferencia (SWI-Prolog)
├── se_app/
│   ├── main.py              Rutas FastAPI
│   ├── motor.py             Puente Python ↔ Prolog (Janus)
│   ├── conocimiento.py      Lectura y edición de se_base_conocimiento + bitácora
│   ├── atenciones.py        Viviendas, atenciones, diagnósticos, citas, historial
│   ├── administracion.py    Usuarios y bitácora (administrador)
│   ├── seguridad.py         Contraseñas scrypt, sesión, roles, bloqueo por intentos
│   ├── alertas.py           Acciones inmediatas de las alertas críticas
│   ├── templates/           Pantallas Jinja2 (diseño B)
│   └── static/              CSS compilado y HTMX
├── scripts/semilla.py       Usuarios de prueba
├── tests/test_motor.py      Validación del motor
└── estilos/app.css          Fuente de Tailwind
```

## Casos de uso cubiertos

| CU | Pantalla |
|---|---|
| CU01 Iniciar sesión | `/login` (bloqueo tras 5 intentos) |
| Registro de cuenta | `/registro` (público, siempre crea consultantes) |
| CU02 Registrar vivienda | `/viviendas` |
| CU03 Diagnosticar falla | `/diagnostico/nuevo` → preguntas Sí/No |
| CU04 Alerta de riesgo crítico | Banner rojo en el reporte |
| CU05 Reporte de diagnóstico | `/diagnostico/{id}/reporte` (Descargar PDF = imprimir) |
| CU06 Agendar cita | Reporte y `/citas` |
| CU07 Consultar historial | `/historial` con filtros |
| CU08 / CU09 Gestionar y validar reglas | `/conocimiento` (experto) |
| Árbol de decisión | `/arbol` (experto y administrador; generado por el motor, con chequeo de coherencia) |
| CU10 Usuarios y roles | `/usuarios` (administrador: crear usuarios con cualquier rol, cambiar rol, bloquear) |
| CU11 Bitácora | `/bitacora` (administrador) |
