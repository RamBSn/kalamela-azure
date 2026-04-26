"""
Tests for the Event Setup module:
- Event settings
- Stage management
- Competition item and criteria management
"""
import pytest


class TestEventSettings:
    def test_get_event_settings_page(self, admin_client):
        r = admin_client.get('/setup/')
        assert r.status_code == 200
        assert b'Event Settings' in r.data

    def test_save_event_settings(self, admin_client):
        r = admin_client.post('/setup/', data={
            'event_name': 'LKC Kalamela 2026',
            'event_date': '2026-05-10',
            'venue': 'London Community Hall',
            'scoresheet_blank_rows': '5',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'LKC Kalamela 2026' in r.data

    def test_event_name_reflected_in_navbar(self, admin_client, app):
        with app.app_context():
            from app.models import EventConfig
            from app import db
            cfg = EventConfig.query.first()
            cfg.event_name = 'My Custom Event'
            db.session.commit()

        r = admin_client.get('/')
        assert b'My Custom Event' in r.data


class TestStages:
    def test_stages_page_loads(self, admin_client):
        r = admin_client.get('/setup/stages')
        assert r.status_code == 200

    def test_add_stage(self, admin_client):
        r = admin_client.post('/setup/stages', data={'name': 'Stage A'},
                        follow_redirects=True)
        assert r.status_code == 200
        assert b'Stage A' in r.data

    def test_add_multiple_stages(self, admin_client):
        for name in ['Stage A', 'Stage B', 'Stage C']:
            admin_client.post('/setup/stages', data={'name': name})
        r = admin_client.get('/setup/stages')
        assert b'Stage A' in r.data
        assert b'Stage B' in r.data
        assert b'Stage C' in r.data

    def test_edit_stage(self, admin_client, app):
        admin_client.post('/setup/stages', data={'name': 'Old Name'})
        with app.app_context():
            from app.models import Stage
            stage = Stage.query.first()
            stage_id = stage.id

        r = admin_client.post(f'/setup/stages/{stage_id}/edit',
                        data={'name': 'New Name'}, follow_redirects=True)
        assert r.status_code == 200
        assert b'New Name' in r.data

    def test_delete_stage(self, admin_client, app):
        admin_client.post('/setup/stages', data={'name': 'ToDelete'})
        with app.app_context():
            from app.models import Stage
            stage = Stage.query.first()
            stage_id = stage.id

        r = admin_client.post(f'/setup/stages/{stage_id}/delete',
                        follow_redirects=True)
        assert r.status_code == 200
        # Verify deleted from DB
        with app.app_context():
            from app.models import Stage
            assert Stage.query.get(stage_id) is None


class TestCompetitionItems:
    def test_items_page_loads(self, admin_client):
        r = admin_client.get('/setup/items')
        assert r.status_code == 200

    def test_add_custom_item(self, admin_client):
        r = admin_client.post('/setup/items/add', data={
            'name': 'Custom Dance',
            'category': 'Junior',
            'item_type': 'solo',
            'max_duration_mins': '5',
            'min_members': '',
            'max_members': '',
            'gender_restriction': '',
            'criteria_name[]': ['Costume', 'Expression', 'Overall'],
            'criteria_max[]': ['30', '40', '30'],
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'Custom Dance' in r.data

    def test_custom_item_listed(self, admin_client, app):
        admin_client.post('/setup/items/add', data={
            'name': 'My Custom Event',
            'category': 'Common',
            'item_type': 'group',
            'max_duration_mins': '10',
            'min_members': '3',
            'max_members': '6',
            'gender_restriction': '',
            'criteria_name[]': ['A', 'B'],
            'criteria_max[]': ['50', '50'],
        })
        with app.app_context():
            from app.models import CompetitionItem
            item = CompetitionItem.query.filter_by(name='My Custom Event').first()
            assert item is not None
            assert item.is_custom is True
            assert item.max_marks_per_judge == 100

    def test_can_delete_builtin_item(self, admin_client_seeded, app_seeded):
        with app_seeded.app_context():
            from app.models import CompetitionItem
            builtin = CompetitionItem.query.filter_by(is_custom=False).first()
            item_id = builtin.id

        r = admin_client_seeded.post(f'/setup/items/{item_id}/delete',
                                     follow_redirects=True)
        assert r.status_code == 200
        with app_seeded.app_context():
            from app.models import CompetitionItem
            assert CompetitionItem.query.get(item_id) is None

    def test_delete_custom_item(self, admin_client, app):
        admin_client.post('/setup/items/add', data={
            'name': 'Deletable Item',
            'category': 'Kids',
            'item_type': 'solo',
            'max_duration_mins': '5',
            'min_members': '',
            'max_members': '',
            'gender_restriction': '',
            'criteria_name[]': ['A'],
            'criteria_max[]': ['100'],
        })
        with app.app_context():
            from app.models import CompetitionItem
            item = CompetitionItem.query.filter_by(name='Deletable Item').first()
            item_id = item.id

        r = admin_client.post(f'/setup/items/{item_id}/delete', follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            from app.models import CompetitionItem
            assert CompetitionItem.query.get(item_id) is None

    def test_edit_item(self, admin_client, app):
        admin_client.post('/setup/items/add', data={
            'name': 'Edit Me',
            'category': 'Kids',
            'item_type': 'solo',
            'max_duration_mins': '5',
            'min_members': '',
            'max_members': '',
            'gender_restriction': '',
            'criteria_name[]': ['X'],
            'criteria_max[]': ['100'],
        })
        with app.app_context():
            from app.models import CompetitionItem
            item = CompetitionItem.query.filter_by(name='Edit Me').first()
            item_id = item.id

        r = admin_client.post(f'/setup/items/{item_id}/edit', data={
            'name': 'Edited Name',
            'category': 'Junior',
            'item_type': 'solo',
            'max_duration_mins': '7',
            'min_members': '',
            'max_members': '',
            'gender_restriction': '',
            'criteria_name[]': ['New Criteria'],
            'criteria_max[]': ['100'],
        }, follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            from app.models import CompetitionItem
            item = CompetitionItem.query.get(item_id)
            assert item.name == 'Edited Name'
            assert item.category == 'Junior'
