from app.services.gft_clinical_sections_auditability import is_auditable_section_row


def test_auditable_with_html_content():
    assert is_auditable_section_row(
        processed_cn='123', processed_nregistro='NR1', requested_section='4.1', row_cn='123', row_nregistro='NR1', row_section='4.1', sync_status='ok', contenido_texto='', contenido_html='<p>x</p>'
    )


def test_auditable_with_text_content():
    assert is_auditable_section_row(
        processed_cn='123', processed_nregistro='NR1', requested_section='4.2', row_cn='123', row_nregistro='NR1', row_section='4.2', sync_status='ok', contenido_texto='texto', contenido_html=''
    )


def test_auditable_with_same_nregistro_and_different_cn():
    assert is_auditable_section_row(
        processed_cn='602914', processed_nregistro='69203', requested_section='4.1', row_cn='602913', row_nregistro='69203', row_section='4.1', sync_status='ok', contenido_texto='t', contenido_html=''
    )


def test_not_auditable_cn_mismatch():
    assert not is_auditable_section_row(
        processed_cn='123', processed_nregistro='NR1', requested_section='4.1', row_cn='999', row_nregistro='NR2', row_section='4.1', sync_status='ok', contenido_texto='x', contenido_html=''
    )


def test_not_auditable_missing_content():
    assert not is_auditable_section_row(
        processed_cn='123', processed_nregistro='NR1', requested_section='4.1', row_cn='999', row_nregistro='NR1', row_section='4.1', sync_status='ok', contenido_texto='   ', contenido_html=' '
    )
