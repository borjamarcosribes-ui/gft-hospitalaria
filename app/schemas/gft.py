from uuid import UUID

from pydantic import BaseModel, Field


class GFTPrincipioActivoRef(BaseModel):
    id: UUID | None = None
    slug: str | None = None
    nombre: str


class GFTAtcRef(BaseModel):
    codigo: str
    nombre: str | None = None
    nivel: str | None = None


class GFTMedicamentoListItem(BaseModel):
    cn: str
    nombre: str | None = None
    presentacion: str | None = None
    forma_farmaceutica: str | None = None
    vias_administracion: list[str] = Field(default_factory=list)
    atc: list[GFTAtcRef] = Field(default_factory=list)
    principios_activos: list[GFTPrincipioActivoRef] = Field(default_factory=list)
    nemonico: str | None = None
    restricciones_hospitalarias: str | None = None
    situacion_financiacion: str | None = None
    url_ficha_tecnica: str | None = None
    url_prospecto: str | None = None


class GFTMedicamentoDetail(GFTMedicamentoListItem):
    observaciones_internas_publicables: str | None = None
    documentos: list[dict] = Field(default_factory=list)


class GFTListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[GFTMedicamentoListItem] = Field(default_factory=list)
