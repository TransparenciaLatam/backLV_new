# models.py
from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Text, DateTime
from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy import Boolean

from .db import Base  # <- esto es el declarative_base()



class Clientes(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre_cliente = Column(String(255), nullable=False)
    email_contacto = Column(String(255), nullable=False, unique=True)
    fecha_registro = Column(TIMESTAMP, server_default=func.now())

    terceros = relationship("Terceros", back_populates="cliente")


class Terceros(Base):
    __tablename__ = "terceros"

    id_tercero = Column(Integer, primary_key=True)
    nombre_tercero = Column(String)
    email = Column(String)
    fecha_registro = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    formularios = Column(Integer, ForeignKey("formularios_generados.id"))

    # Estas son las relaciones que faltaban:
    cliente = relationship("Clientes", back_populates="terceros")
    formulario_generado = relationship("FormularioGenerado", back_populates="terceros")


class PreguntaFormulario(Base):
    __tablename__ = "preguntas_formulario"

    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(String(50), nullable=False)
    texto_pregunta = Column(Text, nullable=False)
    tipo_pregunta = Column(String(50), nullable=False)
    opciones = Column(Text, default="")
    preguntas_relacionadas = Column(Text, default="")
    activa = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())

class FormularioGenerado(Base):
    __tablename__ = "formularios_generados"

    id = Column(Integer, primary_key=True)
    nombre_formulario = Column(String)
    preguntas_ids = Column(String)
    fecha_creacion  = Column(DateTime(timezone=True), server_default=func.now())

    terceros = relationship("Terceros", back_populates="formulario_generado")

