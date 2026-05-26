from app.services.cima_seed_service import extract_nregistro_from_aemps_url


def test_extract_nregistro_from_ft_url():
    assert extract_nregistro_from_aemps_url('https://cima.aemps.es/cima/pdfs/es/ft/12345/12345_ft.pdf') == '12345'


def test_extract_nregistro_from_p_url():
    assert extract_nregistro_from_aemps_url('https://cima.aemps.es/cima/pdfs/es/p/ABCD/ABCD_p.pdf?x=1') == 'ABCD'


def test_extract_nregistro_invalid():
    assert extract_nregistro_from_aemps_url('https://cima.aemps.es/foo.pdf') is None
