from app.services.bifimed_parser import extract_indicaciones_autorizadas


def test_extract_indicaciones_autorizadas_table():
    html = '''<table><tr><th>Indicación autorizada</th><th>Situación expediente indicación</th><th>Resolución expediente de financiación indicación</th></tr><tr><td>Tratamiento de la enfermedad de Wilson.</td><td>Resuelto</td><td>Sí, financiada indicación autorizada</td></tr></table>'''
    out = extract_indicaciones_autorizadas(html)
    assert len(out) == 1
    assert out[0]['indicacion_autorizada'].startswith('Tratamiento')
    assert out[0]['financiada'] is True


def test_extract_indicaciones_autorizadas_no_table():
    assert extract_indicaciones_autorizadas('<html><body>sin tabla</body></html>') == []
