"""
Tests for certificate PDF generation.
"""
import pytest
from tests.conftest import make_item, make_participant, make_entry, score_entry_fully


class TestCertificates:
    def test_certificates_index_loads(self, admin_client):
        r = admin_client.get('/certificates/')
        assert r.status_code == 200

    def test_template_setup_page_loads(self, admin_client):
        r = admin_client.get('/certificates/template')
        assert r.status_code == 200

    def test_save_template_settings(self, admin_client):
        r = admin_client.post('/certificates/template', data={
            'cert_title_text': 'Certificate of Merit',
            'cert_font_colour': '#333333',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'Certificate of Merit' in r.data

    def test_event_certificates_zip_download(self, admin_client, app):
        with app.app_context():
            item = make_item('Cert Test Event', category='Junior')
            p1 = make_participant('Winner One', lkc_id='CW1')
            p2 = make_participant('Winner Two', lkc_id='CW2')
            e1 = make_entry(p1, item)
            e2 = make_entry(p2, item)
            score_entry_fully(e1, j1=90, j2=85, j3=80)
            score_entry_fully(e2, j1=70, j2=65, j3=60)
            item_id = item.id

        r = admin_client.get(f'/certificates/event/{item_id}')
        assert r.status_code == 200
        assert 'zip' in r.content_type

    def test_single_certificate_pdf(self, admin_client, app):
        with app.app_context():
            item = make_item('Single Cert Event', category='Junior')
            p = make_participant('Single Winner', lkc_id='SW1')
            entry = make_entry(p, item)
            score_entry_fully(entry)
            entry_id = entry.id

        r = admin_client.get(f'/certificates/single/{entry_id}/1')
        assert r.status_code == 200
        assert r.content_type == 'application/pdf'
        assert r.data[:4] == b'%PDF'

    def test_award_certificates_zip(self, admin_client, app):
        """award_certificates should return a zip (even if empty)."""
        r = admin_client.get('/certificates/awards')
        assert r.status_code == 200
        assert 'zip' in r.content_type

    def test_event_certificates_redirect_when_no_scores(self, admin_client, app):
        with app.app_context():
            item = make_item('Unscored Event', category='Junior')
            p = make_participant('Unscored', lkc_id='US1')
            make_entry(p, item)
            item_id = item.id

        r = admin_client.get(f'/certificates/event/{item_id}',
                       follow_redirects=True)
        assert r.status_code == 200
        assert b'No scored entries' in r.data or b'no scored' in r.data.lower()

    def test_certificate_pdf_content(self, app):
        """Unit test the PDF generator directly."""
        with app.app_context():
            from app.pdf.certificate import generate_certificate
            import io
            import pypdf
            pdf = generate_certificate(
                event_name='Test Kalamela 2026',
                participant_name='Arjun Kumar',
                item_name='Folk Dance',
                category='Junior',
                position='1st Prize',
                event_date='01 May 2026',
            )
            assert isinstance(pdf, bytes)
            assert pdf[:4] == b'%PDF'
            assert len(pdf) > 1000
            # Verify it's a valid PDF with at least 1 page
            reader = pypdf.PdfReader(io.BytesIO(pdf))
            assert len(reader.pages) >= 1
