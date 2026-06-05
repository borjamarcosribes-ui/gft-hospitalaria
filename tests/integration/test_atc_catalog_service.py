from app.services.atc_catalog_service import (
    atc_catalog_fingerprint,
    get_atc_level,
    get_atc_parent_code,
    get_atc_title,
    get_atc_titles_map,
)


def test_atc_catalog_resolves_titles_parents_and_levels(db_session):
    assert get_atc_title("A", db_session) == "Tracto alimentario y metabolismo"
    assert get_atc_title("A02", db_session) == "Agentes para el tratamiento de alteraciones causadas por ácidos"
    assert get_atc_title("A02AD", db_session) == "Asociaciones y complejos de compuestos de aluminio, calcio y magnesio"
    assert get_atc_parent_code("A02AD03", db_session) == "A02AD"
    assert get_atc_level("A", db_session) == 1
    assert get_atc_level("A02", db_session) == 2
    assert get_atc_level("A02A", db_session) == 3
    assert get_atc_level("A02AD", db_session) == 4
    assert get_atc_level("A02AD03", db_session) == 5


def test_atc_titles_map_comes_from_backend_catalog(db_session):
    titles = get_atc_titles_map(db_session)

    assert titles["A"] == "Tracto alimentario y metabolismo"
    assert titles["A02"] == "Agentes para el tratamiento de alteraciones causadas por ácidos"
    assert len(titles) >= 4248
    assert atc_catalog_fingerprint(db_session) == atc_catalog_fingerprint(db_session)
