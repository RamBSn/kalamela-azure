"""
Tests for judge score sheet PDF generation.
"""
import pytest
from tests.conftest import make_item, make_participant, make_entry


class TestScoresheets:
    def test_scoresheets_index_loads(self, admin_client):
        r = admin_client.get('/scoresheets/')
        assert r.status_code == 200

    def test_scoresheet_page_shows_events_with_entries(self, admin_client, app):
        with app.app_context():
            item = make_item('Score Sheet Event', category='Junior')
            p = make_participant()
            make_entry(p, item)

        r = admin_client.get('/scoresheets/')
        assert r.status_code == 200
        assert b'Score Sheet Event' in r.data

    def test_generate_scoresheet_pdf(self, admin_client, app):
        with app.app_context():
            item = make_item('PDF Test Event', category='Junior')
            p = make_participant()
            make_entry(p, item)
            item_id = item.id

        r = admin_client.get(f'/scoresheets/generate/{item_id}')
        assert r.status_code == 200
        assert r.content_type == 'application/pdf'
        # PDF magic bytes
        assert r.data[:4] == b'%PDF'

    def test_scoresheet_pdf_has_three_pages(self, admin_client, app):
        """Each judge gets one page — 3 pages total."""
        import io
        import pypdf

        with app.app_context():
            item = make_item('Three Page Test', category='Junior')
            for i in range(3):
                p = make_participant(f'Performer {i}', lkc_id=f'L{i}')
                make_entry(p, item)
            item_id = item.id

        r = admin_client.get(f'/scoresheets/generate/{item_id}')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'
        # Verify 3 pages (one per judge) using pypdf
        reader = pypdf.PdfReader(io.BytesIO(r.data))
        assert len(reader.pages) == 3

    def test_scoresheet_includes_entry_names(self, admin_client, app):
        import io
        import pypdf

        with app.app_context():
            item = make_item('Name Check Event', category='Junior')
            p = make_participant('Test Performer Name', lkc_id='LT1')
            make_entry(p, item)
            item_id = item.id

        r = admin_client.get(f'/scoresheets/generate/{item_id}')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'
        # Extract text from PDF pages and verify participant name is present
        reader = pypdf.PdfReader(io.BytesIO(r.data))
        all_text = ''.join(page.extract_text() or '' for page in reader.pages)
        assert 'Test Performer Name' in all_text

    def test_generate_404_for_nonexistent_item(self, admin_client):
        r = admin_client.get('/scoresheets/generate/99999')
        assert r.status_code == 404
