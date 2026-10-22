/*  =====================================================================
    SISTEMA EXPERTO DE DIAGNOSTICO DE VIVIENDA
    MOTOR DE INFERENCIA  -  SWI-Prolog

    Universidad Manuela Beltran - Ingenieria de Software
    Sistemas Expertos - Ing. Jose Marcial Tellez Gomez
    Lina Maria Brinez Rodriguez & Victor Alfonso Alarcon Ospina - 2026

    La base de conocimiento NO esta escrita en este archivo (RNF19): la
    aplicacion la lee de MySQL (se_base_conocimiento) y la carga con
    cargar/3, que la convierte en estos hechos:

      pregunta(Codigo, Categoria, Texto, EnunciadoSi, EnunciadoNo)
      hipotesis(Codigo, Categoria, Diagnostico, Urgencia, Certeza,
                Especialista, Accion, Validada)
      condicion(Hipotesis, Pregunta, Valor, Orden)
          Valor = 1 (Si) | 0 (No);  Orden = 1 es el If, >= 2 los And.

    Cada hipotesis con sus condiciones es un granulo, es decir, la regla
      If <condicion 1> And <condicion 2> ... Then <hipotesis>

    Los HECHOS de una consulta llegan como una lista Pregunta-Valor con
    las respuestas que el usuario ya dio (memoria de trabajo).

    Estrategia (seccion "Estrategia de inferencia" del manual):
      1. Encadenamiento hacia atras: solo se pregunta lo necesario para
         confirmar o descartar las hipotesis que siguen siendo posibles.
      2. Mientras exista una pregunta pendiente, se formula.
      3. Sin preguntas pendientes, se dispara la regla cuyas condiciones
         se cumplen todas. Si hubiera varias, gana la de mayor severidad
         y despues la de mayor factor de certeza.
      4. Si ninguna se cumple: conclusion por defecto (RNF22).
    ===================================================================== */

:- module(motor,
          [ cargar/3,
            paso/4,
            estado_hipotesis/3,
            explicacion/2,
            total_reglas/1
          ]).

:- dynamic pregunta/5, hipotesis/8, condicion/4.


/* ---------------------------------------------------------------------
   Carga de la base de conocimiento
   Cada lista llega desde Python como lista de tuplas, que Janus
   convierte en terminos -(A, B, ...). Los codigos se guardan como
   atomos y los textos como strings.
   --------------------------------------------------------------------- */

%!  cargar(+Preguntas, +Hipotesis, +Condiciones) is det.
cargar(Preguntas, Hipotesis, Condiciones) :-
    retractall(pregunta(_, _, _, _, _)),
    retractall(hipotesis(_, _, _, _, _, _, _, _)),
    retractall(condicion(_, _, _, _)),
    forall(member(-(C, Cat, T, Si, No), Preguntas),
           ( atom_string(AC, C), atom_string(ACat, Cat),
             assertz(pregunta(AC, ACat, T, Si, No)) )),
    forall(member(-(C, Cat, Dx, U, FC, Esp, Acc, Val), Hipotesis),
           ( atom_string(AC, C), atom_string(ACat, Cat), atom_string(AU, U),
             assertz(hipotesis(AC, ACat, Dx, AU, FC, Esp, Acc, Val)) )),
    forall(member(-(H, P, V, O), Condiciones),
           ( atom_string(AH, H), atom_string(AP, P),
             assertz(condicion(AH, AP, V, O)) )).

%!  total_reglas(-N) is det.
total_reglas(N) :-
    aggregate_all(count, hipotesis(_, _, _, _, _, _, _, _), N).


/* ---------------------------------------------------------------------
   Memoria de trabajo
   --------------------------------------------------------------------- */

% hechos(+Lista, -Hechos): normaliza la lista que llega de Python
% (tuplas "codigo"-valor) a pares atomo-valor.
hechos(Lista, Hechos) :-
    maplist(hecho, Lista, Hechos).

hecho(-(P, V), AP-V) :- atom_string(AP, P).

respondida(P, Hechos) :- memberchk(P-_, Hechos).


/* ---------------------------------------------------------------------
   Evaluacion de reglas
   --------------------------------------------------------------------- */

% compatible(+H, +Hechos): ninguna respuesta dada contradice la regla H.
% La regla sigue siendo posible.
compatible(H, Hechos) :-
    forall(condicion(H, P, V, _),
           ( memberchk(P-X, Hechos) -> X =:= V ; true )).

% cumple(+H, +Hechos): todas las condiciones de H estan respondidas y
% coinciden. La regla se dispara.
cumple(H, Hechos) :-
    forall(condicion(H, P, V, _),
           ( memberchk(P-X, Hechos), X =:= V )).

% Severidad para la resolucion de conflictos: menor numero, mayor prioridad.
severidad('Critica', 1).
severidad('Alta',    2).
severidad('Media',   3).
severidad('Baja',    4).


%!  siguiente_pregunta(+Categoria, +Hechos, -Pregunta) is semidet.
%
%   Encadenamiento hacia atras: entre las hipotesis de la categoria que
%   siguen siendo posibles, toma la primera condicion aun sin responder
%   (menor orden y, a igual orden, menor codigo de hipotesis). Equivale a
%   la consulta B3 del script 04_consultas_granulos.sql.
siguiente_pregunta(Cat, Hechos, P) :-
    findall(O-H-P0,
            ( hipotesis(H, Cat, _, _, _, _, _, _),
              compatible(H, Hechos),
              condicion(H, P0, _, O),
              \+ respondida(P0, Hechos) ),
            Pendientes),
    msort(Pendientes, [_-_-P|_]).

%!  diagnosticar(+Categoria, +Hechos, -Hipotesis) is semidet.
%
%   Dispara la regla que se cumple. Si hubiera mas de una, resuelve el
%   conflicto por severidad y luego por factor de certeza. Equivale a la
%   consulta B5.
diagnosticar(Cat, Hechos, H) :-
    findall(S-NegFC-H0,
            ( hipotesis(H0, Cat, _, U, FC, _, _, _),
              cumple(H0, Hechos),
              severidad(U, S),
              NegFC is -FC ),
            Disparadas),
    msort(Disparadas, [_-_-H|_]).


%!  paso(+Categoria, +Respuestas, -Tipo, -Codigo) is det.
%
%   Un ciclo del motor. Tipo es:
%     pregunta    - Codigo es la siguiente pregunta a formular
%     diagnostico - Codigo es la hipotesis concluida
%     ninguno     - conclusion por defecto, Codigo = ''
paso(Cat0, Respuestas, Tipo, Codigo) :-
    atom_string(Cat, Cat0),
    hechos(Respuestas, Hechos),
    (   siguiente_pregunta(Cat, Hechos, P)
    ->  Tipo = pregunta, Codigo = P
    ;   diagnosticar(Cat, Hechos, H)
    ->  Tipo = diagnostico, Codigo = H
    ;   Tipo = ninguno, Codigo = ''
    ).


/* ---------------------------------------------------------------------
   Explicacion (modulo de explicacion del sistema experto)
   --------------------------------------------------------------------- */

%!  estado_hipotesis(+Categoria, +Respuestas, -Estados) is det.
%
%   Estado de cada regla de la categoria frente a la memoria de trabajo:
%   descartada, confirmada o en_evaluacion. Lo usa el panel de
%   razonamiento que ve el experto.
estado_hipotesis(Cat0, Respuestas, Estados) :-
    atom_string(Cat, Cat0),
    hechos(Respuestas, Hechos),
    findall(H-E,
            ( hipotesis(H, Cat, _, _, _, _, _, _),
              estado(H, Hechos, E) ),
            Estados).

estado(H, Hechos, descartada)    :- \+ compatible(H, Hechos), !.
estado(H, Hechos, confirmada)    :- cumple(H, Hechos), !.
estado(_, _,      en_evaluacion).

%!  explicacion(+Hipotesis, -Pasos) is det.
%
%   Ruta If / And de la regla, en orden: lista de Pregunta-Valor.
explicacion(H0, Pasos) :-
    atom_string(H, H0),
    findall(O-(P-V), condicion(H, P, V, O), L),
    msort(L, Ordenada),
    pairs_values(Ordenada, Pasos).
