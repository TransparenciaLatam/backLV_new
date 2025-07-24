# schemas.py
from pydantic import BaseModel, EmailStr, field_validator
from typing import List,Optional
from datetime import datetime



class IndicesRequest(BaseModel):
    indices: List[int]



#primer esquema, para traer clientes con sus terceros

class TerceroOut(BaseModel):
    id_tercero: int
    nombre_tercero: str
    email: str
    fecha_registro: datetime
    cliente_id: int

    class Config:
        orm_mode = True  


class ClienteConTercerosOut(BaseModel):
    id: int
    nombre_cliente: str
    email_contacto: str
    fecha_registro: datetime
    terceros: List[TerceroOut] 

    class Config:
        orm_mode = True


##Esquemas para crear clientes

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


##esquema para traer terceros junto con su cliente y formulario asignado

class ClienteRelacionadoTercero(BaseModel):
    id: int
    nombre_cliente: str
    email_contacto: str
    fecha_registro: datetime

    class Config:
        orm_mode = True

class FormularioRelacionadoTercero(BaseModel):
    id: int
    nombre_formulario: str
    preguntas_ids: str
    fecha_creacion: datetime

    class Config:
        orm_mode = True

class TerceroOut2(BaseModel):
    id_tercero: int
    nombre_tercero: str
    email: str
    fecha_registro: Optional[datetime]
    
    cliente: ClienteRelacionadoTercero
    formulario_generado: Optional[FormularioRelacionadoTercero]

    class Config:
        orm_mode = True






##esquema para crear tercero

class TerceroCreate(BaseModel):
    nombre_tercero: str
    email: EmailStr
    cliente_id: int



##ESquema para traer el formulario con sus preguntas, por su id

class SubPregunta(BaseModel):
    index: int
    texto_pregunta: Optional[str] = None
    tipo_pregunta: Optional[str] = None
    opciones: Optional[list] = None
    detonador: Optional[str] = None

class PreguntaAdaptada(BaseModel):
    id: int
    categoria: str
    preguntas: List[SubPregunta]

class FormularioGeneradoOutPreguntas(BaseModel):
    id: int
    nombre_formulario: str
    fecha_creacion: datetime
    preguntas: List[PreguntaAdaptada]

    class Config:
        orm_mode = True








class PreguntaFormularioOut(BaseModel):
    id: int
    categoria: str
    texto_pregunta: str
    tipo_pregunta: str
    opciones: str
    preguntas_relacionadas: str
    activa: bool
    fecha_creacion: datetime

    class Config:
        orm_mode = True




##Formularioo para cargar informacion en el dashboard

class FormularioGeneradoOutInfo(BaseModel):
    id: int
    nombre_formulario: str
    preguntas_ids: List[int]
    fecha_creacion: datetime

    @field_validator("preguntas_ids", mode="before")
    @classmethod
    def split_preguntas_ids(cls, value):
        if isinstance(value, str):
            return [int(x) for x in value.split(",") if x.strip()]
        return value

    class Config:
        orm_mode = True







class SubPreguntaSchema(BaseModel):
    index: int
    texto_pregunta: Optional[str] = None
    tipo_pregunta: Optional[str] = None
    opciones: Optional[List[str]] = None
    detonador: Optional[str] = None

class GrupoPreguntasSchema(BaseModel):
    id: int
    categoria: str
    preguntas: List[SubPreguntaSchema]




class FormularioCreate(BaseModel):
    nombre_formulario: str
    preguntas_ids: List[int]















