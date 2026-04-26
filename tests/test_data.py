"""
Tests for data management: backup, restore, reset, export.
"""
import os
import json
import pytest
from tests.conftest import make_item, make_participant, make_entry, score_entry_fully


class TestDataManagement:
    def test_data_index_loads(self, admin_client):
        r = admin_client.get('/data/')
        assert r.status_code == 200

    def test_manual_backup_creates_file(self, admin_client, app):
        r = admin_client.post('/data/backup', follow_redirects=True)
        assert r.status_code == 200
        assert b'Backup created' in r.data

        backup_dir = app.config['BACKUP_FOLDER']
        backups = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
        assert len(backups) >= 1
        assert any('manual' in f for f in backups)

    def test_reset_requires_confirmation(self, admin_client):
        r = admin_client.post('/data/reset', data={'confirm_reset': ''},
                        follow_redirects=True)
        assert r.status_code == 200
        assert b'RESET' in r.data  # warning shown

    def test_reset_clears_participant_data(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant('To Be Deleted', lkc_id='LR1')
            make_entry(p, item)

        r = admin_client.post('/data/reset', data={'confirm_reset': 'RESET'},
                        follow_redirects=True)
        assert r.status_code == 200

        with app.app_context():
            from app.models import Participant, Entry
            assert Participant.query.count() == 0
            assert Entry.query.count() == 0

    def test_reset_preserves_event_config(self, admin_client, app):
        with app.app_context():
            make_item('Preserved Item', category='Junior')

        admin_client.post('/data/reset', data={'confirm_reset': 'RESET'})

        with app.app_context():
            from app.models import EventConfig, CompetitionItem
            assert EventConfig.query.count() == 1
            assert CompetitionItem.query.filter_by(
                name='Preserved Item'
            ).first() is not None

    def test_reset_creates_auto_backup(self, admin_client, app):
        backup_dir = app.config['BACKUP_FOLDER']
        before = set(os.listdir(backup_dir))

        admin_client.post('/data/reset', data={'confirm_reset': 'RESET'})

        after = set(os.listdir(backup_dir))
        new_files = after - before
        assert any('pre_reset' in f for f in new_files)

    def test_export_json(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant('Export Test', lkc_id='LE1')
            make_entry(p, item)

        r = admin_client.get('/data/export?format=json')
        assert r.status_code == 200
        assert r.content_type == 'application/json'

        data = json.loads(r.data)
        assert 'participants' in data
        assert 'entries' in data
        assert 'scores' in data
        names = [p['full_name'] for p in data['participants']]
        assert 'Export Test' in names

    def test_export_csv(self, admin_client, app):
        with app.app_context():
            make_participant('CSV User', lkc_id='LC1')

        r = admin_client.get('/data/export?format=csv')
        assert r.status_code == 200
        assert 'text/csv' in r.content_type
        assert b'CSV User' in r.data

    def test_download_backup(self, admin_client, app):
        # Create a backup first
        admin_client.post('/data/backup')
        backup_dir = app.config['BACKUP_FOLDER']
        backups = sorted(
            [f for f in os.listdir(backup_dir) if f.endswith('.db')]
        )
        assert backups
        filename = backups[-1]

        r = admin_client.get(f'/data/download/{filename}')
        assert r.status_code == 200

    def test_download_nonexistent_backup_redirects(self, admin_client):
        r = admin_client.get('/data/download/nonexistent_backup.db',
                       follow_redirects=True)
        assert r.status_code == 200
        assert b'not found' in r.data.lower()

    def test_delete_backup(self, admin_client, app):
        admin_client.post('/data/backup')
        backup_dir = app.config['BACKUP_FOLDER']
        backups = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
        filename = backups[0]

        r = admin_client.post(f'/data/delete-backup/{filename}',
                        follow_redirects=True)
        assert r.status_code == 200
        assert not os.path.exists(os.path.join(backup_dir, filename))

    def test_restore_requires_db_file(self, admin_client):
        import io
        r = admin_client.post('/data/restore', data={
            'backup_file': (io.BytesIO(b'not a db'), 'test.txt')
        }, content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        assert b'Only .db' in r.data
