from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Query, APIRouter, Depends
from fastapi import Path, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from collections import defaultdict

from psycopg2.extras import RealDictCursor

from pydantic import BaseModel
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from backendlinking.schemas import ClientCreate, ClientOut, ClienteConTercerosOut, FormularioCreate, FormularioGeneradoOutInfo, FormularioGeneradoOutPreguntas, GrupoPreguntasSchema
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





# @app.post("/subir-archivo")
# async def subir_archivo(archivo: UploadFile = File(...)):
#     extension = Path(archivo.filename).suffix.lower()
#     content_type = archivo.content_type

#     # Verificar extensión permitida
#     if extension not in TIPOS_PERMITIDOS:
#         raise HTTPException(status_code=400, detail="Extensión de archivo no permitida")

#     # Verificar MIME type declarado
#     if TIPOS_PERMITIDOS[extension] != content_type:
#         raise HTTPException(status_code=400, detail="Tipo MIME no coincide con la extensión")

#     # Leer bytes y validar tamaño
#     contenido = await archivo.read()
#     if len(contenido) > MAX_TAMANO_BYTES:
#         raise HTTPException(status_code=413, detail="Archivo demasiado grande")

#     # Verificar contenido real usando python-magic
#     tipo_real = magic.from_buffer(contenido, mime=True)
#     if tipo_real != content_type:
#         raise HTTPException(status_code=400, detail="El contenido del archivo es sospechoso")

#     # Volver al inicio del stream
#     archivo.file.seek(0)

#     # Guardar con nombre aleatorio
#     nuevo_nombre = f"{uuid.uuid4().hex}{extension}"
#     destino = UPLOAD_DIR / nuevo_nombre

#     with destino.open("wb") as f:
#         shutil.copyfileobj(archivo.file, f)

#     # URL pública para recuperar el archivo
#     url_publica = f"http://localhost:8000/archivos/{nuevo_nombre}"

#     return {"url": url_publica}


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






app.include_router(router)





























