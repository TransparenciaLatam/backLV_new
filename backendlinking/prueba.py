from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Query, APIRouter, Depends
from fastapi import Path
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from db import get_connection
from pydantic import BaseModel
from typing import Optional

from sqlalchemy.orm import Session

from db import get_db
from models import Clientes, Terceros
from schemas import ClientOut, ClientCreate, ClienteConTercerosOut, TerceroOut
from typing import List, Optional


app = FastAPI(title="Linking Values API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


class PreguntaUpdate(BaseModel):
    texto_pregunta: str
    tipo_pregunta: str
    pregunta_relacionada_texto: Optional[str] = None


class PreguntaCreate(BaseModel):
    categoria: str
    texto_pregunta: str
    tipo_pregunta: str
    pregunta_relacionada_texto: Optional[str] = None


class FormularioInput(BaseModel):
    tercero_id: int
    preguntas_ids: str  # Ej: "1,2,3" como texto plano

class FormularioUpdate(BaseModel):
    preguntas_ids: list[int]  # o str si estás guardando como string







#trae todas las preguntas

@app.get("/preguntas_formulario")
async def get_terceros():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM preguntas_formulario ORDER BY categoria;")
            preguntas_raw = cursor.fetchall()

        preguntas_limpias = preparar_preguntas_formulario(preguntas_raw)
        
        ordenadas = ordenar_preguntas(preguntas_limpias)

        return {"preguntas": ordenadas}

    finally:
        conn.close()




# filtra por categoria
@app.get("/preguntas_formulario/categoria/{categoria}")
async def get_preguntas_por_categoria(categoria: str = Path(..., description="Categoría de las preguntas")):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM preguntas_formulario WHERE categoria = %s;",
                (categoria,)
            )
            preguntas_raw = cursor.fetchall()

        preguntas_limpias = preparar_preguntas_formulario(preguntas_raw)
        
        ordenadas = ordenar_preguntas(preguntas_limpias)

        return {"preguntas": ordenadas}
        
    finally:
        conn.close()


#filtra por id
@app.get("/preguntas_formulario/id/{id}")
async def get_pregunta_por_id(id: int = Path(..., description="ID de la pregunta")):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM preguntas_formulario WHERE id = %s;",
                (id,)
            )
            pregunta = cursor.fetchone()
            if pregunta is None:
                raise HTTPException(status_code=404, detail="Pregunta no encontrada")
            return {"pregunta": pregunta}
    finally:
        conn.close()


#actualiza pregunta por id
@app.put("/preguntas_formulario/{id}")
async def actualizar_pregunta(id: int, pregunta: PreguntaUpdate):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE preguntas_formulario
                SET texto_pregunta = %s,
                    tipo_pregunta = %s,
                    pregunta_relacionada_texto = %s
                WHERE id = %s;
                """,
                (pregunta.texto_pregunta, pregunta.tipo_pregunta, pregunta.pregunta_relacionada_texto, id)
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="No se encontró una pregunta con ese id.")
            conn.commit()
            return {"message": "Pregunta actualizada correctamente"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")
    finally:
        conn.close()



#guarda pregunta nueva
@app.post("/preguntas_formulario/")
async def crear_pregunta(pregunta: PreguntaCreate):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO preguntas_formulario (categoria, texto_pregunta, tipo_pregunta, pregunta_relacionada_texto)
                VALUES (%s, %s, %s, %s);
                """,
                (pregunta.categoria, pregunta.texto_pregunta, pregunta.tipo_pregunta, pregunta.pregunta_relacionada_texto)
            )
            conn.commit()
            return {"message": "Pregunta creada correctamente"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear la pregunta: {str(e)}")
    finally:
        conn.close()















#agregar un formulario nuevo a un tercero
@app.post("/formulario_tercero")
async def crear_formulario(formulario: FormularioInput):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO formulario_por_terceros (tercero_id, preguntas_ids) VALUES (%s, %s);",
                (formulario.tercero_id, formulario.preguntas_ids)
            )
            conn.commit()
            return {"message": "Formulario guardado exitosamente"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")
    finally:
        conn.close()



#obtener un formulario de un tercero
@app.get("/formulario_tercero/{id_tercero}")
async def obtener_formulario(id_tercero: int):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM formulario_por_terceros WHERE tercero_id = %s;",
                (id_tercero,)
            )
            resultados = cursor.fetchall()
            if not resultados:
                raise HTTPException(status_code=404, detail="Formulario no encontrado para ese tercero.")
            return {"formularios": resultados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener: {str(e)}")
    finally:
        conn.close()





#editar un formulario de un tercero
@app.put("/formulario_tercero/{id_tercero}")
async def actualizar_formulario(id_tercero: int, formulario: FormularioUpdate):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE formulario_por_terceros SET preguntas_ids = %s WHERE tercero_id = %s;",
                (formulario.preguntas_ids, id_tercero)
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="No se encontró un formulario con ese id_tercero.")
            conn.commit()
            return {"message": "Formulario actualizado correctamente"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")
    finally:
        conn.close()









router = APIRouter()

@router.get("/clientes", response_model=List[ClientOut])
def obtener_clientes(nombre: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Clientes)
    if nombre:
        query = query.filter(Clientes.nombre_cliente.ilike(f"%{nombre}%"))
    return query.all()


@router.get("/clientes/{id}", response_model=ClientOut)
def obtener_cliente_por_id(id: int, db: Session = Depends(get_db)):
    cliente = db.query(Clientes).filter(Clientes.id == id).first()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente


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




@router.get("/clientes_terceros/{id}", response_model=ClienteConTercerosOut)
def obtener_cliente_y_terceros(id: int, db: Session = Depends(get_db)):
    cliente = db.query(Clientes).filter(Clientes.id == id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente

@router.get("/clientes_terceros", response_model=List[ClienteConTercerosOut])
def obtener_todos_los_clientes_con_terceros(db: Session = Depends(get_db)):
    clientes = db.query(Clientes).all()
    return clientes



@router.get("/terceros/{cliente_id}", response_model=List[TerceroOut])
def obtener_terceros(cliente_id: int, db: Session = Depends(get_db)):
    query = db.query(Terceros).filter(Terceros.cliente_id == cliente_id).all()
    if not query:
        raise HTTPException(status_code=404, detail="No hay terceros para ese id")
    return query


app.include_router(router)
























###############################################################################################################3333
#FUNCIONES
#llevar a archivo func.py



def preparar_preguntas_formulario(preguntas_raw):

    preguntas_limpias = []
        
    for p in preguntas_raw:

        categoria = p["categoria"].strip() if p["categoria"] else None
        tipo_pregunta = p["tipo_pregunta"].strip() if p["tipo_pregunta"] else None
        texto_pregunta = p["texto_pregunta"].strip() if p["texto_pregunta"] else None

        # Buscar ID de pregunta relacionada
        pregunta_relacionada_texto = p.get("pregunta_relacionada_texto")
        if pregunta_relacionada_texto:
            relacionada = next(
                (pr for pr in preguntas_raw if pr["texto_pregunta"].strip() == pregunta_relacionada_texto.strip()),
                None
            )
            id_relacionada = relacionada["id"] if relacionada else None
        else:
            id_relacionada = None

        # Procesar opciones: dejar como lista o null
        opciones = p.get("opciones")
        if isinstance(opciones, str) and opciones.strip():
            raw = opciones.strip()
            if "," in raw:
                opciones = [o.strip() for o in raw.split(",")]
            elif "\n" in raw or "- " in raw:
                opciones = [o.strip("- ").strip() for o in raw.splitlines() if o.strip()]
            elif ":" in raw:
                opciones = [o.strip(": ").strip() for o in raw.splitlines() if o.strip()]
            else:
                opciones = [raw]
        else:
            opciones = None

        preguntas_limpias.append({
            "id": p["id"],
            "categoria": categoria,
            "texto_pregunta": texto_pregunta,
            "tipo_pregunta": tipo_pregunta,
            "relacion": id_relacionada,
            "opciones": opciones
        })
    
    return preguntas_limpias








def ordenar_preguntas(preguntas_limpias):
    from collections import defaultdict

    # 1. Definir orden deseado
    orden_personalizado = [
        "informacion_general_gobernanza",
        "derechos_humanos",
        "sostenibilidad_medio_ambiente",
        "anticorrupcion"
    ]

    # 2. Agrupar por categoría
    categorias = defaultdict(list)
    preguntas_dict = {p["id"]: p for p in preguntas_limpias}

    for p in preguntas_limpias:
        categoria = p["categoria"]
        categorias[categoria].append(p)

    preguntas_ordenadas = []

    # 3. Procesar en el orden deseado
    for categoria in orden_personalizado:
        if categoria not in categorias:
            continue

        preguntas = categorias[categoria]
        preguntas.sort(key=lambda x: x["id"])
        ya_agregados = set()
        bloque_categoria = []

        for p in preguntas:
            if p["id"] in ya_agregados:
                continue

            # Si tiene una pregunta relacionada
            if p["relacion"]:
                relacionada = preguntas_dict.get(p["relacion"])
                if relacionada and relacionada["id"] not in ya_agregados:
                    bloque_categoria.append(relacionada)
                    ya_agregados.add(relacionada["id"])

            bloque_categoria.append(p)
            ya_agregados.add(p["id"])

        preguntas_ordenadas.extend(bloque_categoria)

    return preguntas_ordenadas





