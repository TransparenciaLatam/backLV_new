from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Query
from fastapi import Path
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from db import get_connection
from pydantic import BaseModel
from typing import Optional


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



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)





#trae todas las preguntas

@app.get("/preguntas_formulario")
async def get_terceros():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM preguntas_formulario ORDER BY categoria;")
            return {"preguntas": cursor.fetchall()}
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
            return {"preguntas": cursor.fetchall()}
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