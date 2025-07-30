from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Query, APIRouter, Depends
from fastapi import Path, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from collections import defaultdict

from psycopg2.extras import RealDictCursor

from pydantic import BaseModel
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from schemas import ClientCreate, ClientOut, ClienteConTercerosOut, FormularioCreate, FormularioGeneradoOutInfo, FormularioGeneradoOutPreguntas, GrupoPreguntasSchema
from config import allow_origins

from database.db import get_connection
from database.db import get_db
from database.models import *
from schemas import *
from typing import List, Optional


import re
import shutil
import uuid
#import magic  # python-magic
import os


app = FastAPI(title="Linking Values API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

router = APIRouter()


#pip install httpx
# import httpx

# # Tu clave secreta de reCAPTCHA v3
# RECAPTCHA_SECRET_KEY = "6Lc2kJQrAAAAABbFc_9ximQMb0f6RCcnD0ny9jaE"

# class FormData(BaseModel):
#     nombre: str
#     email: str
#     recaptcha_token: str

# @app.post("/verificar-recaptcha")
# async def verificar_recaptcha(data: FormData):
#     async with httpx.AsyncClient() as client:
#         response = await client.post(
#             "https://www.google.com/recaptcha/api/siteverify",
#             data={
#                 "secret": RECAPTCHA_SECRET_KEY,
#                 "response": data.recaptcha_token,
#             }
#         )

#     result = response.json()

#     if not result.get("success"):
#         raise HTTPException(status_code=400, detail="Verificación reCAPTCHA fallida")

#     return {
#         "success": result["success"],
#         "score": result.get("score", 0.0),
#         "action": result.get("action", "")
#     }







# # Carpeta de subida
# UPLOAD_DIR = Path("archivos_subidos")
# UPLOAD_DIR.mkdir(exist_ok=True)

# Extensiones y MIME válidos
TIPOS_PERMITIDOS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Tamaño máximo permitido: 5 MB
MAX_TAMANO_BYTES = 5 * 1024 * 1024

##Funciones --------------------------------------------------------------------------------------------------

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1

#funcion para manejar las opciones y los detonantes
def parsear_opciones_avanzado(cadena):
    def extraer_bloques(s):
        # Encuentra bloques correctamente balanceados
        bloques = []
        stack = []
        inicio = None
        for i, c in enumerate(s):
            if c == '(':
                if not stack:
                    inicio = i
                stack.append(c)
            elif c == ')':
                stack.pop()
                if not stack and inicio is not None:
                    bloques.append(s[inicio+1:i])  # sin paréntesis
        return bloques

    def procesar_bloque(bloque):
        # Si tiene sub-bloques, es anidado
        if '(' in bloque:
            return [tuple(b.split(",")) for b in extraer_bloques(bloque)]
        else:
            return tuple(bloque.split(","))

    bloques = extraer_bloques(cadena)
    return [procesar_bloque(b) for b in bloques]

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

#Esta funcion maneja las preguntas crudas de la base de datos y las rearma
#para poder interpretarse en el frontend!
def armarPregunta(preguntas):

    pregunta_dict = {}
    pregunta_dict["id"] = preguntas["id"]
    pregunta_dict["categoria"] = preguntas["categoria"]
    pregunta_dict["preguntas"] = []
    index = 1
    
    lista_preguntas = {

        "index" : index,
        "texto_pregunta": preguntas["texto_pregunta"],
        "tipo_pregunta": preguntas["tipo_pregunta"]

    }

    if preguntas["opciones"]:

        opciones = parsear_opciones_avanzado(preguntas["opciones"]) 

        lista_preguntas["opciones"] = opciones[0]
        pregunta_dict["preguntas"].append(lista_preguntas)
     

        if preguntas["preguntas_relacionadas"]:

            preguntas_relacionadas = parsear_opciones_avanzado(preguntas["preguntas_relacionadas"])
        
            contador_opciones = 1 
            detonador_index_1 = 0
            detonador_index_2 = 0
            vueltas = 0
            
            for preg in preguntas_relacionadas: 

                dictt = {}
                detonador = opciones[detonador_index_1][detonador_index_2]
                index +=1 

                if any(preg):

                    if isinstance(preg, list):

                        for pr in preg:
                        
                            dictt = {
                                "index" : index,
                                "detonador" : detonador,
                                "texto_pregunta" : pr[0],
                                "tipo_pregunta" : pr[1]                                   
                            }
                            pregunta_dict["preguntas"].append(dictt)
                    else:

                        dictt = {
                                "index" : index,
                                "detonador" : detonador,
                                "texto_pregunta" : preg[0],
                                "tipo_pregunta" : preg[1]                                   
                            }
                        
                        if contador_opciones < len(opciones) and opciones[contador_opciones]:

                            dictt["opciones"] = opciones[contador_opciones]
                            contador_opciones += 1
                        
                        pregunta_dict["preguntas"].append(dictt)

                else:

                    dictt = {
                                "index" : index 
                                  
                            }

                    pregunta_dict["preguntas"].append(dictt)
                
                vueltas += 1
                detonador_index_2 += 1 
               
                if vueltas == 2:
                    vueltas = 0
                    detonador_index_1 +=1
                    detonador_index_2 = 0                       
                            
    else:
        pregunta_dict["preguntas"].append(lista_preguntas)

    return pregunta_dict

def ordenar_preguntas(preguntas: list[dict]) -> list[dict]:
    """
    Ordena una lista de preguntas por 'categoria' y luego por 'id'.
    
    :param preguntas: Lista de diccionarios con preguntas.
    :return: Lista ordenada.
    """
    return sorted(preguntas, key=lambda p: (p["categoria"], p["id"]))

##!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

## Funcion principal para trae preguntas
@app.get("/preguntas_formulario")
async def get_preguntas_activas(db: Session = Depends(get_db)):
    preguntas_raw = (
        db.query(PreguntaFormulario)
        .filter(PreguntaFormulario.activa == True)
        .order_by(PreguntaFormulario.categoria)
        .all()
    )

    preguntas_dicts = [p.__dict__ for p in preguntas_raw]
    for p in preguntas_dicts:
        p.pop("_sa_instance_state", None)

    preguntas_ordenadas = ordenar_preguntas(preguntas_dicts)
    lista_preguntas = []
    for i in preguntas_ordenadas:
        aux = armarPregunta(i)
        lista_preguntas.append(aux)
    return {"preguntas": lista_preguntas}

##arreglando formulario para agregar preguntas
@app.post("/nueva_pregunta")
def crear_pregunta(pregunta: PreguntaFormularioBase, db: Session = Depends(get_db)):
    nueva = PreguntaFormulario(
        categoria=pregunta.categoria,
        texto_pregunta=pregunta.texto_pregunta,
        tipo_pregunta=pregunta.tipo_pregunta,
        opciones=pregunta.opciones,
        preguntas_relacionadas=pregunta.preguntas_relacionadas,
        activa=True
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return {"id": nueva.id, "mensaje": "Pregunta creada con éxito"}



##Funcion para traer preguntas por categoria!!!

@app.get("/preguntas_por_categoria")
async def get_preguntas_por_categoria(db: Session = Depends(get_db)):
    preguntas_raw = (
        db.query(PreguntaFormulario)
        .filter(PreguntaFormulario.activa == True)
        .order_by(PreguntaFormulario.categoria)
        .all()
    )

    preguntas_dicts = [p.__dict__ for p in preguntas_raw]
    for p in preguntas_dicts:
        p.pop("_sa_instance_state", None)

    preguntas_ordenadas = ordenar_preguntas(preguntas_dicts)

    categorias_dict = defaultdict(list)
    for pregunta in preguntas_ordenadas:
        categoria = pregunta.get("categoria", "Sin categoría")
        categorias_dict[categoria].append(armarPregunta(pregunta))

    resultado = [{"categoria": cat, "preguntas": preguntas} for cat, preguntas in categorias_dict.items()]
    
    return resultado






##!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!111
## Funcion para analizar carga de archivos




TIPOS_PERMITIDOS = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # .xlsx
}

@router.post("/validar-archivo")
async def validar_archivo(archivo: UploadFile = File(...)):
    if archivo.content_type not in TIPOS_PERMITIDOS:
        return JSONResponse(status_code=400, content={"aprobado": False, "detalle": "Tipo de archivo no permitido"})

    contenido = await archivo.read()

    if len(contenido) > 10 * 1024 * 1024:
        return JSONResponse(status_code=400, content={"aprobado": False, "detalle": "El archivo excede el tamaño máximo permitido"})

    # Aquí podrías aplicar más validaciones (como antivirus, etc)

    return {"aprobado": True}




# # Montar carpeta de archivos estáticos
# app.mount("/archivos", StaticFiles(directory=UPLOAD_DIR), name="archivos")





##Funcion para traer clienntes por lista
@router.get("/clientes", response_model=List[ClientOut])
def obtener_clientes(nombre: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Clientes)
    if nombre:
        query = query.filter(Clientes.nombre_cliente.ilike(f"%{nombre}%"))
    return query.all()


#funcion para traer clientes por id
@router.get("/clientes/{id}", response_model=ClientOut)
def obtener_cliente_por_id(id: int, db: Session = Depends(get_db)):
    cliente = db.query(Clientes).filter(Clientes.id == id).first()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente


#funcion para crear un nuevo cliente
@router.post("/clientes", response_model=ClientOut, status_code=201)
def crear_cliente(cliente: ClientCreate, db: Session = Depends(get_db)):
    nuevo_cliente = Clientes(
        nombre_cliente=cliente.nombre_cliente,
        email_contacto=cliente.email_contacto
    )
    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)
    return nuevo_cliente

#funcion para traer tercero y su cliente
@router.get("/clientes_terceros/{id}", response_model=ClienteConTercerosOut)
def obtener_cliente_y_terceros(id: int, db: Session = Depends(get_db)):
    cliente = db.query(Clientes).filter(Clientes.id == id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente

#funcion para traer todos los clientes y sus terceros
@router.get("/clientes_terceros", response_model=List[ClienteConTercerosOut])
def obtener_todos_los_clientes_con_terceros(db: Session = Depends(get_db)):
    clientes = db.query(Clientes).all()
    return clientes

#funcion para traer terceros de un cliente por id
@router.get("/terceros/{cliente_id}", response_model=List[TerceroOut])
def obtener_terceros(cliente_id: int, db: Session = Depends(get_db)):
    query = db.query(Terceros).filter(Terceros.cliente_id == cliente_id).all()
    if not query:
        raise HTTPException(status_code=404, detail="No hay terceros para ese id")
    return query

##Funcion para traer terceros y su cliente referncia y formulario referido
@router.get("/terceros", response_model=List[TerceroOut2])
def obtener_terceros(db: Session = Depends(get_db)):
    terceros = db.query(Terceros).options(
        joinedload(Terceros.cliente),
        joinedload(Terceros.formulario_generado)
    ).all()
    
    if not terceros:
        raise HTTPException(status_code=404, detail="No hay terceros registrados")
    return terceros


##Funcion para guardar tercero

@router.post("/terceros/")
def crear_tercero(tercero: TerceroCreate, db: Session = Depends(get_db)):
    nuevo_tercero = Terceros(
        nombre_tercero=tercero.nombre_tercero,
        email=tercero.email,
        cliente_id=tercero.cliente_id,
        fecha_registro=None,        # opcional, podés también usar datetime.utcnow() si querés registrarlo ahora
        formularios=None
    )

    db.add(nuevo_tercero)
    db.commit()
    db.refresh(nuevo_tercero)

    return {
        "cliente_id": nuevo_tercero.id_tercero,
        "nombre_tercero": nuevo_tercero.nombre_tercero,
        "email": nuevo_tercero.email
    }

##Funciones para traer formularios para mostrar en dashboard..
@router.get("/formularios", response_model=List[FormularioGeneradoOutInfo])
def obtener_todos_los_formularios(db: Session = Depends(get_db)):
    formularios = db.query(FormularioGenerado).all()
    return formularios

#Formulario
@router.get("/formularios/{formulario_id}", response_model=FormularioGeneradoOutPreguntas)
def obtener_formulario_por_id(formulario_id: int, db: Session = Depends(get_db)):
    formulario = db.query(FormularioGenerado).filter(FormularioGenerado.id == formulario_id).first()

    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")

    # Convertir string de ids en lista de enteros
    try:
        preguntas_ids = [int(pid.strip()) for pid in formulario.preguntas_ids.split(",") if pid.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Error al parsear preguntas_ids")

    preguntas = db.query(PreguntaFormulario).filter(PreguntaFormulario.id.in_(preguntas_ids)).all()

    preguntas_dicts = [p.__dict__ for p in preguntas]
    for p in preguntas_dicts:
        p.pop("_sa_instance_state", None)

    preguntas_ordenadas = ordenar_preguntas(preguntas_dicts)
    lista_preguntas = []
    for i in preguntas_ordenadas:
        aux = armarPregunta(i)
        lista_preguntas.append(aux)


    return {
        "id": formulario.id,
        "nombre_formulario": formulario.nombre_formulario,
        "fecha_creacion": formulario.fecha_creacion,
        "preguntas": lista_preguntas
    }



class IdsRequest(BaseModel):
    ids: List[int]

@router.post("/formularios", response_model=List[GrupoPreguntasSchema])
def obtener_preguntas_por_ids_directo(
    ids: List[int] = Body(...),
    db: Session = Depends(get_db)
):
    preguntas = db.query(PreguntaFormulario).filter(PreguntaFormulario.id.in_(ids)).all()

    if not preguntas:
        raise HTTPException(status_code=404, detail="No se encontraron preguntas con los IDs proporcionados")

    preguntas_dicts = [p.__dict__ for p in preguntas]
    for p in preguntas_dicts:
        p.pop("_sa_instance_state", None)

    preguntas_ordenadas = ordenar_preguntas(preguntas_dicts)
    lista_preguntas = []
    for i in preguntas_ordenadas:
        aux = armarPregunta(i)
        lista_preguntas.append(aux)

    return lista_preguntas




##Esta funcion rrecibe un id de formulario y filtra por categorias

@router.get(
    "/formularios/{formulario_id}/categoria/{categoria}",
    response_model=List[GrupoPreguntasSchema],
    summary="Obtiene preguntas activas de un formulario por categoría"
)
def obtener_preguntas_por_categoria(
    formulario_id: int,
    categoria: str,
    db: Session = Depends(get_db)
):
    formulario = db.query(FormularioGenerado).filter(FormularioGenerado.id == formulario_id).first()
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")

    try:
        preguntas_ids = list(map(int, formulario.preguntas_ids.split(',')))
    except Exception:
        raise HTTPException(status_code=400, detail="Formato inválido en preguntas_ids")

    preguntas = (
        db.query(PreguntaFormulario)
        .filter(
            PreguntaFormulario.id.in_(preguntas_ids),
            PreguntaFormulario.categoria == categoria,
            PreguntaFormulario.activa == True
        )
        .all()
    )

    preguntas_dicts = [p.__dict__ for p in preguntas]
    for p in preguntas_dicts:
        p.pop("_sa_instance_state", None)

    preguntas_ordenadas = ordenar_preguntas(preguntas_dicts)
    lista_preguntas = []
    for i in preguntas_ordenadas:
        aux = armarPregunta(i)
        lista_preguntas.append(aux)

    return lista_preguntas









def crear_formulario(db: Session, datos: FormularioCreate):
    preguntas_ids_str = ",".join(str(id) for id in datos.preguntas_ids)

    nuevo_formulario = FormularioGenerado(
        nombre_formulario=datos.nombre_formulario,
        preguntas_ids=preguntas_ids_str
    )

    db.add(nuevo_formulario)
    db.commit()
    db.refresh(nuevo_formulario)

    return nuevo_formulario

@router.post("/guardar_formulario")
def guardar_formulario(formulario: FormularioCreate, db: Session = Depends(get_db)):
    return crear_formulario(db, formulario)









##Funcion para conseguir estadisticas

@app.get("/estadisticas")
def get_estadisticas(db: Session = Depends(get_db)):
    total_empresas = db.query(Clientes).count()
    total_proveedores = db.query(Terceros).count()
    total_formularios = db.query(FormularioGenerado).count()
    return {
        "empresas": total_empresas,
        "proveedores": total_proveedores,
        "formularios" : total_formularios
    }







##Peticion para el inicio de tercero
##ESta funcion trae informacion de tercero, de su cliente y formulario. y ademas las categorias que posee en su formulario


@router.get("/tercero_info/{id_tercero}")
def obtener_info_tercero(id_tercero: int, db: Session = Depends(get_db)):
    # Obtener el tercero + cliente relacionado
    tercero = db.query(Terceros).filter(Terceros.id_tercero == id_tercero).first()
    if not tercero:
        raise HTTPException(status_code=404, detail="Tercero no encontrado")

    cliente = tercero.cliente
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    formulario = db.query(FormularioGenerado).filter(FormularioGenerado.id == tercero.formularios).first()
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")

    # Obtener categorías de las preguntas del formulario
    try:
        preguntas_ids = [int(pid) for pid in formulario.preguntas_ids.split(',') if pid.strip().isdigit()]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar preguntas_ids: {str(e)}")

    preguntas = db.query(PreguntaFormulario).filter(PreguntaFormulario.id.in_(preguntas_ids)).all()

    # Agrupar por categorías únicas
    categorias = list(set([preg.categoria for preg in preguntas if preg.categoria]))

    # Armar la respuesta
    return {
        "tercero": {
            "nombre": tercero.nombre_tercero,
            "email": tercero.email,
            "cliente_id": tercero.cliente_id,
            "formulario_id": tercero.formularios
        },
        "cliente": {
            "nombre": cliente.nombre_cliente,
            "email": cliente.email_contacto
        },
        "categorias": categorias
    }





##Funcion para traer terceros por id y ademas sus formularios correspondientes


@router.get("/clientes/{cliente_id}/terceros", response_model=List[TerceroSchema])
def obtener_terceros_por_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(Clientes).filter(Clientes.id == cliente_id).first()
    
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    return cliente.terceros


##Funcion para asignar formularios
@router.post("/asignar_formulario")
def asignar_formulario_a_tercero(
    datos: AsignacionFormulario,
    db: Session = Depends(get_db)
):
    tercero = db.query(Terceros).filter(Terceros.id_tercero == datos.id_tercero).first()

    if not tercero:
        raise HTTPException(status_code=404, detail="Tercero no encontrado")

    tercero.formularios = datos.formulario_id
    db.commit()

    return {"mensaje": "ok!"}




















app.include_router(router)





























