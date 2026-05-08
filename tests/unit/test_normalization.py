import math
import pytest
from app.services.normalization_service import (
    classify_observaciones_revision, normalize_cn, normalize_estado_editorial, normalize_principio_activo, NormalizationError
)


def test_classify_cases():
    assert classify_observaciones_revision("SÍ") == "incluido"
    assert classify_observaciones_revision("SI") == "incluido"
    assert classify_observaciones_revision("guía") == "pendiente_revision"
    assert classify_observaciones_revision("guia") == "pendiente_revision"
    assert classify_observaciones_revision("NO") == "excluido"
    assert classify_observaciones_revision("no guia") == "excluido"
    assert classify_observaciones_revision("bloquear") == "excluido"
    assert classify_observaciones_revision("No aparece en Clínic") == "excluido"
    assert classify_observaciones_revision("sin planificador o consumo") == "excluido"
    assert classify_observaciones_revision("SI?") == "pendiente_revision"
    assert classify_observaciones_revision("NO?") == "pendiente_revision"
    assert classify_observaciones_revision("???") == "pendiente_revision"
    assert classify_observaciones_revision("") == "pendiente_revision"
    assert classify_observaciones_revision(None) == "pendiente_revision"
    assert classify_observaciones_revision(float('nan')) == "pendiente_revision"


def test_normalize_cn_cases():
    assert normalize_cn(123456) == "123456"
    assert normalize_cn("123456.0") == "123456"
    assert normalize_cn(" 123456 ") == "123456"
    assert normalize_cn("00123456") == "00123456"
    with pytest.raises(NormalizationError):
        normalize_cn(None)
    with pytest.raises(NormalizationError):
        normalize_cn(float('nan'))


def test_normalize_estado_editorial():
    assert normalize_estado_editorial(None) == "borrador"
    assert normalize_estado_editorial("") == "borrador"
    assert normalize_estado_editorial(math.nan) == "borrador"
    assert normalize_estado_editorial("validado") == "validado"
    assert normalize_estado_editorial("publicado") == "publicado"
    with pytest.raises(NormalizationError):
        normalize_estado_editorial("raro")


def test_normalize_principio_activo():
    assert normalize_principio_activo("Ácido acetilsalicílico") == "acido acetilsalicilico"
