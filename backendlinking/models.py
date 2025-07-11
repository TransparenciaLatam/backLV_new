# models.py
from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, func
from sqlalchemy.orm import relationship

from db import Base  # <- esto es el declarative_base()

class Clientes(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre_cliente = Column(String(255), nullable=False)
    email_contacto = Column(String(255), nullable=False, unique=True)
    fecha_registro = Column(TIMESTAMP, server_default=func.now())

    terceros = relationship("Terceros", back_populates="cliente")



class Terceros(Base):
    __tablename__ = "terceros"

    id_tercero = Column(Integer, primary_key=True, index=True)
    nombre_tercero = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    fecha_registro = Column(TIMESTAMP, server_default=func.now())

    # ForeignKey que referencia al id de Clientes
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)

    # Relación hacia Cliente (opcional pero útil)
    cliente = relationship("Clientes", back_populates="terceros")
