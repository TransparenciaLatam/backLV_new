import psycopg2
from config import DB_CONFIG

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def obtener_preguntas():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, categoria, texto_pregunta, tipo_pregunta, pregunta_relacionada_texto
        FROM preguntas_formulario
    """)
    filas = cursor.fetchall()

    cursor.close()
    conn.close()

    return filas
