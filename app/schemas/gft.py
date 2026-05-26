from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GFTPrincipioActivoRef(BaseModel):
    id: UUID | None = None
    slug: str | None = None
    nombre: str


class GFTPrincipioActivoIndexItem(BaseModel):
    id: UUID
    slug: str
    nombre: str
    letra: str
    count: int


class GFTPrincipioActivoIndexResponse(BaseModel):
    items: list[GFTPrincipioActivoIndexItem] = Field(default_factory=list)


class GFTAtcRef(BaseModel):
    codigo: str
    nombre: str | None = None
    nivel: str | None = None


class GFTAtcIndexItem(BaseModel):
    codigo: str
    nombre: str | None = None
    nivel: str
    count: int


class GFTAtcIndexResponse(BaseModel):
    items: list[GFTAtcIndexItem] = Field(default_factory=list)


class GFTDocumentoCimaRef(BaseModel):
    tipo: int | str | None = None
    url: str | None = None
    urlHtml: str | None = None
    secc: str | None = None
    fecha: str | None = None
    titulo: str | None = None
    nombre: str | None = None


class GFTIndicacionAutorizadaBifimed(BaseModel):
    indicacion_autorizada: str | None = None
    situacion_expediente_indicacion: str | None = None
    resolucion_expediente_financiacion_indicacion: str | None = None
    financiada: bool | None = None


class GFTFinanciacionDetalle(BaseModel):
    situacion_financiacion: str | None = None
    condiciones_financiacion_restringidas: str | None = None
    condiciones_especiales_financiacion: str | None = None
    estado_nomenclator: str | None = None
    aportacion_usuario: str | None = None
    subgrupo_atc: str | None = None
    last_synced_at: datetime | None = None
    indicaciones_autorizadas: list[GFTIndicacionAutorizadaBifimed] | None = None


class GFTClinicalSummaryAuto(BaseModel):
    source_status: str | None = None
    generated_at: datetime | None = None
    resumen_general: str | None = None
    indicaciones: str | None = None
    posologia: str | None = None
    ajuste_renal: str | None = None
    ajuste_hepatico: str | None = None
    contraindicaciones: str | None = None
    advertencias: str | None = None
    embarazo: str | None = None
    lactancia: str | None = None
    fuentes: dict | list | None = None
    warnings: list | dict | None = None


class GFTMedicamentoListItem(BaseModel):
    cn: str
    nombre: str | None = None
    presentacion: str | None = None
    forma_farmaceutica: str | None = None
    forma_farmaceutica_simplificada: str | None = None
    vias_administracion: list[str] = Field(default_factory=list)
    atc: list[GFTAtcRef] = Field(default_factory=list)
    principios_activos: list[GFTPrincipioActivoRef] = Field(default_factory=list)
    nemonico: str | None = None
    restricciones_hospitalarias: str | None = None
    ajuste_insuficiencia_renal: str | None = None
    ajuste_insuficiencia_hepatica: str | None = None
    precauciones_embarazo: str | None = None
    precauciones_lactancia: str | None = None
    situacion_financiacion: str | None = None
    url_ficha_tecnica: str | None = None
    url_prospecto: str | None = None
    fecha_ficha_tecnica: date | None = None
    fecha_prospecto: date | None = None
    indicaciones_ficha_tecnica: str | None = None


class GFTMedicamentoDetail(GFTMedicamentoListItem):
    observaciones_publicables: str | None = None
    documentos: list[GFTDocumentoCimaRef] = Field(default_factory=list)
    financiacion_detalle: GFTFinanciacionDetalle | None = None
    resumen_clinico_auto: GFTClinicalSummaryAuto | None = None


class GFTListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[GFTMedicamentoListItem] = Field(default_factory=list)
