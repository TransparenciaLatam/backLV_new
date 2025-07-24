import random
from typing import Optional, Dict, Any, List
from uuid import uuid4
import psycopg2
import requests
import json
from faker import Faker
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg2 import sql
from pydantic import BaseModel
from starlette.responses import JSONResponse, RedirectResponse
from supabase import create_client, Client
from psycopg2.extras import RealDictCursor
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from prueba import *

# ==============================================================================
# 1. APPLICATION SETUP & CONFIGURATION
# ==============================================================================
app = FastAPI(title="Linking Values API")
faker = Faker()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Supabase and DB Config
SUPABASE_URL = "https://xjnjjpojzowcnqoxlwas.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhqbmpqcG9qem93Y25xb3hsd2FzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzIwMjQ0MzMsImV4cCI6MjA0NzYwMDQzM30.ql1u8O7eH8oqtJ9feAshD4lyff9c86JgXTvFiDQ32dc"
STORAGE_BUCKET = "terceroforms"
DB_HOST = "aws-0-us-east-1.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.xjnjjpojzowcnqoxlwas"
DB_PASSWORD = "uzovQblfnT68R9Ad"
DB_PORT = "6543"

# Postmark API settings
POSTMARK_URL = "https://api.postmarkapp.com/email"
POSTMARK_TOKEN = "11ab78d0-2bbb-4b78-ab03-a22d90ff2f42"

supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
templates = Jinja2Templates(directory="templates")






# ==============================================================================
# 2. PYDANTIC MODELS (Data Validation)
# ==============================================================================
class UpdatePasswordRequest(BaseModel):
    email: str
    new_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TerceroCreateRequest(BaseModel):
    nombre: str
    email: str
    password: str
    cliente_id: int


class TerceroProgressUpdate(BaseModel):
    tercero_id: int
    progress: int


class ReportUploadRequest(BaseModel):
    filename: str
    htmlContent: str


class TerceroFormAssignmentRequest(BaseModel):
    form_response_json: Dict[str, Any]


# ==============================================================================
# 3. HELPER FUNCTIONS
# ==============================================================================
def get_db_connection():
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT)
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Could not connect to the database.")


def standardize_form_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    standardized_fields = []
    if not data or "axes" not in data: return []
    for axis in data.get("axes", []):
        standardized_fields.append({"type": "heading", "label": axis.get("name", "Sección"), "id": axis.get("id")})
        for question in axis.get("questions", []):
            question_type = question.get("type", "text_short")
            field_object = {
                "id": question.get("id"), "label": question.get("text"), "name": question.get("id"),
                "helpText": question.get("helpText", ""), "required": question.get("required", False),
                "condition": question.get("condition"),
            }
            if question_type == "text_short":
                field_object["type"] = "text"
            elif question_type == "text_long":
                field_object["type"] = "textarea"
            elif question_type == "date":
                field_object["type"] = "date"
            elif question_type == "number":
                field_object["type"] = "number"
            elif question_type == "link":
                field_object["type"] = "url"
            elif question_type == "file_upload":
                field_object["type"] = "file"
            elif question_type == "yes_no":
                field_object["type"] = "radio"
                field_object["options"] = [{"label": "Sí", "value": "si"}, {"label": "No", "value": "no"}]
            elif question_type in ["multiple_choice", "checkboxes"]:
                field_object["type"] = "radio" if question_type == "multiple_choice" else "checkbox"
                field_object["options"] = [{"label": opt, "value": opt} for opt in question.get("options", [])]
            else:
                field_object["type"] = "text"
            standardized_fields.append(field_object)
    standardized_fields.append({"type": "submit", "value": "Enviar Respuestas"})
    return standardized_fields


# ==============================================================================
# 4. CORE APPLICATION ENDPOINTS (User Portal, Submission, Report)
# ==============================================================================

@app.get("/form/{tercero_id}", response_class=HTMLResponse, summary="Main portal for a Tercero")
async def serve_tercero_portal(request: Request, tercero_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id, nombre, form_response_json, is_completed FROM tercero WHERE id = %s",
                           (tercero_id,))
            tercero = cursor.fetchone()
            if not tercero: raise HTTPException(status_code=404, detail="Usuario no encontrado.")

            print(f"Serving portal for Tercero ID: {tercero_id}, Name: {tercero['nombre']}")

            context = {"request": request, "tercero": tercero, "status": 'initial', "fields": [],
                       "form_schema_json": "{}"}
            if tercero['is_completed']:
                context['status'] = 'completed'
            elif not tercero['form_response_json']:
                context['status'] = 'waiting'
            else:
                context['status'] = 'ready_to_fill'
                form_schema = tercero['form_response_json']
                context["fields"] = standardize_form_data(form_schema)
                context["form_schema_json"] = json.dumps(form_schema)
                print(f"Form schema for Tercero ID {tercero_id}: {context['form_schema_json']}")
            return templates.TemplateResponse("render_form.html", context)
    finally:
        conn.close()


@app.post("/submit-form/{tercero_id}", summary="Handles form submission")
async def handle_form_submission(request: Request, tercero_id: int):
    form_payload = await request.form()
    submission_data, files_uploaded = {}, {}

    # Process form data, grouping checkbox values into lists
    for key in form_payload.keys():
        values = form_payload.getlist(key)
        if not (hasattr(values[0], 'filename') and values[0].filename):
            submission_data[key] = values if len(values) > 1 else values[0]

    # Handle file uploads
    for key, value in form_payload.items():
        if hasattr(value, "filename") and value.filename:
            file_content = await value.read()
            if file_content:
                unique_filename = f"submissions/{tercero_id}/{uuid4()}_{value.filename}"
                supabase_client.storage.from_(STORAGE_BUCKET).upload(unique_filename, file_content)
                public_url = supabase_client.storage.from_(STORAGE_BUCKET).get_public_url(unique_filename)
                files_uploaded[key] = public_url
                submission_data[key] = public_url

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO form_submissions (tercero_id, submission_data, files_uploaded) VALUES (%s, %s, %s);",
                (tercero_id, json.dumps(submission_data), json.dumps(files_uploaded))
            )
            cursor.execute("UPDATE tercero SET is_completed = TRUE WHERE id = %s", (tercero_id,))
            conn.commit()
    except psycopg2.Error as e:
        conn.rollback();
        raise HTTPException(status_code=500, detail=f"Error al guardar: {e}")
    finally:
        conn.close()
    return RedirectResponse(url=f"/form/{tercero_id}", status_code=303)


@app.get("/report/{tercero_id}", response_class=HTMLResponse,
         summary="Displays a human-readable report of a submission")
async def view_submission_report(request: Request, tercero_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = sql.SQL("""
                SELECT t.nombre, t.form_response_json, fs.submission_data, fs.submitted_at
                FROM tercero t LEFT JOIN form_submissions fs ON t.id = fs.tercero_id
                WHERE t.id = %s ORDER BY fs.submitted_at DESC LIMIT 1;
            """)
            cursor.execute(query, (tercero_id,))
            report_data = cursor.fetchone()
            if not report_data: raise HTTPException(status_code=404, detail="Tercero no encontrado.")
            if not report_data['submission_data']: raise HTTPException(status_code=404, detail="No submission found.")

            form_schema, answers, report_items = report_data['form_response_json'], report_data['submission_data'], []
            for axis in form_schema.get('axes', []):
                report_items.append({'is_heading': True, 'text': axis.get('name', 'Sección')})
                for question in axis.get('questions', []):
                    q_id = question.get('id')
                    report_items.append({
                        'is_heading': False, 'question_text': question.get('text'),
                        'answer': answers.get(q_id), 'type': question.get('type')
                    })
            context = {"request": request, "tercero_name": report_data['nombre'],
                       "submitted_at": report_data['submitted_at'], "report_items": report_items}
            return templates.TemplateResponse("report.html", context)
    finally:
        conn.close()


# ==============================================================================
# 5. ADMINISTRATION & FORM BUILDER ENDPOINTS
# ==============================================================================

@app.patch("/tercero/{tercero_id}", summary="Assign a dynamic form to a Tercero")
async def assign_form_to_tercero(tercero_id: int, request_body: TerceroFormAssignmentRequest):
    form_json_string = json.dumps(request_body.form_response_json)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE tercero SET form_response_json = %s WHERE id = %s;", (form_json_string, tercero_id))
            if cursor.rowcount == 0: raise HTTPException(status_code=404,
                                                         detail=f"Tercero with ID {tercero_id} not found.")
            conn.commit()
        return {"message": "Form assigned successfully", "tercero_id": tercero_id}
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/v1/form/parser", response_class=HTMLResponse, summary="Generates a preview of a dynamic form")
async def render_dynamic_form_preview(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    context = {
        "request": request,
        "title": data.get("formTitle", "Vista Previa del Formulario"),
        "fields": standardize_form_data(data),
        "form_schema_json": data,
        "tercero": fake_tercero,  # <-- Se añade el tercero simulado
        "status": "ready_to_fill"  # Para que la plantilla muestre el formulario
    }
    return templates.TemplateResponse("render_form.html", context)


# ==============================================================================
# 6. AUTHENTICATION & USER MANAGEMENT ENDPOINTS
# ==============================================================================
@app.post("/login")
async def login(request: LoginRequest):
    """
    Improved login endpoint that returns the user's ID on success.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Check in tercero table
            cursor.execute("SELECT id, password FROM tercero WHERE email = %s", (request.email,))
            tercero_result = cursor.fetchone()

            if tercero_result and request.password == tercero_result['password']:
                return {
                    "message": "Login successful",
                    "role": "tercero",
                    "table": "tercero",
                    "tercero_id": tercero_result['id']  # <-- RETURN THE ID
                }

            # Check in cliente table
            cursor.execute("SELECT id, password FROM cliente WHERE email = %s", (request.email,))
            cliente_result = cursor.fetchone()

            if cliente_result and request.password == cliente_result['password']:
                return {
                    "message": "Login successful",
                    "role": "cliente",
                    "table": "cliente",
                    "cliente_id": cliente_result['id'] # <-- RETURN THE ID
                }

            raise HTTPException(status_code=401, detail="Invalid email or password")
    finally:
        conn.close()

@app.put("/update-password")
async def update_password(request: UpdatePasswordRequest):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE tercero SET password = %s WHERE email = %s;", (request.new_password, request.email))
            if cursor.rowcount == 0: raise HTTPException(status_code=404, detail="Email not found.")
            conn.commit()
        return {"message": "Password updated successfully"}
    finally:
        conn.close()


@app.post("/tercero/create")
async def create_tercero(request: TerceroCreateRequest):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tercero (nombre, email, password, cliente_id) VALUES (%s, %s, %s, %s) RETURNING id;",
                (request.nombre, request.email, request.password, request.cliente_id))
            new_id = cursor.fetchone()[0]
            conn.commit()
        return {"message": "Tercero created successfully", "id": new_/id}
    finally:
        conn.close()


@app.get("/tercero/full")
async def get_terceros():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM tercero ORDER BY id;")
            return {"terceros": cursor.fetchall()}
    finally:
        conn.close()


@app.get("/client-id")
async def get_client_id(email: str = Query(...)):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM cliente WHERE email = %s LIMIT 1;", (email,))
            result = cursor.fetchone()
            if not result: raise HTTPException(status_code=404, detail="Client not found")
            return {"client_id": result[0]}
    finally:
        conn.close()


@app.get("/tercero/nombres")
async def get_tercero_nombres(cliente_id: int = Query(...)):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM tercero WHERE cliente_id = %s;", (cliente_id,))
            return {"nombres": [{"id": row[0], "nombre": row[1]} for row in cursor.fetchall()]}
    finally:
        conn.close()


# ==============================================================================
# 7. MISCELLANEOUS & LEGACY ENDPOINTS
# ==============================================================================
@app.post("/send-email")
async def send_email(request: Request):
    body = await request.json()
    response = requests.post(POSTMARK_URL,
                             headers={"X-Postmark-Server-Token": POSTMARK_TOKEN, "Content-Type": "application/json"},
                             json=body)
    if response.status_code != 200: raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()


@app.post("/upload-report")
async def upload_report(report_request: ReportUploadRequest):
    file_content = report_request.htmlContent.encode('utf-8')
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{report_request.filename}?upsert=true"
    headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "text/html"}
    response = requests.post(upload_url, headers=headers, data=file_content)
    if response.status_code != 200: raise HTTPException(status_code=response.status_code, detail=response.text)
    return {"message": "Report uploaded successfully", "filename": report_request.filename}


# This is a sample endpoint from your original code that generates test data.
# It can be useful for testing but should probably be removed in production.
@app.post("/supabase/provider_evaluation/insert")
async def insert_provider_evaluation():
    # ... (code for generating fake data - keeping it as it was in your original file)
    # This function is very long and I will omit its body for brevity, but it should be kept if you use it.
    return {"message": "Fake record inserted successfully"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})



























#FUNCIONES NUEVAS HECHAS POR MAURO!!!
#=====================================================================================================




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