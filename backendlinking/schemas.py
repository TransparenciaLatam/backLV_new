# schemas.py
from pydantic import BaseModel, EmailStr
from typing import List
from datetime import datetime

class ClientOut(BaseModel):
    id: int
    nombre_cliente: str
    email_contacto: str
    fecha_registro: datetime

    class Config:
        orm_mode = True  # Esto permite convertir desde modelos SQLAlchemy


class ClientCreate(BaseModel):
    nombre_cliente: str
    email_contacto: EmailStr



class TerceroOut(BaseModel):
    id_tercero: int
    nombre_tercero: str
    email: str
    fecha_registro: datetime
    cliente_id: int 

    class Config:
        orm_mode = True  


class TerceroCreate(BaseModel):
    nombre_tercero: str
    email: EmailStr
    cliente_id: int



class ClienteConTercerosOut(BaseModel):
    id: int
    nombre_cliente: str
    email_contacto: str
    fecha_registro: datetime
    terceros: List[TerceroOut]  # Este campo hace la magia

    class Config:
        orm_mode = True