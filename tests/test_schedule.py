"""
Tests for the Schedule module:
- Stage assignment
- Running order
- Status updates
"""
import pytest
from tests.conftest import make_item, make_participant, make_entry


class TestSchedule:
    def test_schedule_index_loads(self, admin_client):
        r = admin_client.get('/schedule/')
        assert r.status_code == 200

    def test_stage_view_loads(self, admin_client, app):
        with app.app_context():
            from app.models import Stage
            from app import db
            stage = Stage(name='Stage A', display_order=1)
            db.session.add(stage)
            db.session.commit()
            stage_id = stage.id

        r = admin_client.get(f'/schedule/stage/{stage_id}')
        assert r.status_code == 200
        assert b'Stage A' in r.data

    def test_assign_entry_to_stage(self, admin_client, app):
        with app.app_context():
            from app.models import Stage
            from app import db
            stage = Stage(name='Stage B', display_order=1)
            db.session.add(stage)
            db.session.commit()
            stage_id = stage.id

            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            entry_id = entry.id

        r = admin_client.post('/schedule/assign', data={
            'entry_id': str(entry_id),
            'stage_id': str(stage_id),
        }, follow_redirects=True)
        assert r.status_code == 200

        with app.app_context():
            from app.models import Entry
            e = Entry.query.get(entry_id)
            assert e.stage_id == stage_id
            assert e.running_order == 1

    def test_unassign_entry(self, admin_client, app):
        with app.app_context():
            from app.models import Stage
            from app import db
            stage = Stage(name='Stage C', display_order=1)
            db.session.add(stage)
            db.session.commit()
            stage_id = stage.id

            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            entry.stage_id = stage_id
            entry.running_order = 1
            db.session.commit()
            entry_id = entry.id

        admin_client.post('/schedule/assign', data={
            'entry_id': str(entry_id),
            'stage_id': '',
        })
        with app.app_context():
            from app.models import Entry
            e = Entry.query.get(entry_id)
            assert e.stage_id is None
            assert e.running_order is None

    def test_running_order_increments(self, admin_client, app):
        with app.app_context():
            from app.models import Stage
            from app import db
            stage = Stage(name='Stage D', display_order=1)
            db.session.add(stage)
            db.session.commit()
            stage_id = stage.id

            item = make_item()
            p1 = make_participant('P1', lkc_id='L1')
            p2 = make_participant('P2', lkc_id='L2')
            e1 = make_entry(p1, item)
            e2 = make_entry(p2, item)
            e1_id, e2_id = e1.id, e2.id

        admin_client.post('/schedule/assign', data={'entry_id': str(e1_id), 'stage_id': str(stage_id)})
        admin_client.post('/schedule/assign', data={'entry_id': str(e2_id), 'stage_id': str(stage_id)})

        with app.app_context():
            from app.models import Entry
            e1 = Entry.query.get(e1_id)
            e2 = Entry.query.get(e2_id)
            assert e1.running_order == 1
            assert e2.running_order == 2

    def test_status_update_waiting_to_performing(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            entry_id = entry.id

        r = admin_client.post(f'/schedule/entry/{entry_id}/status',
                        data={'status': 'performing'}, follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            from app.models import Entry
            e = Entry.query.get(entry_id)
            assert e.status == 'performing'

    def test_status_update_to_completed(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            entry_id = entry.id

        admin_client.post(f'/schedule/entry/{entry_id}/status', data={'status': 'completed'})
        with app.app_context():
            from app.models import Entry
            e = Entry.query.get(entry_id)
            assert e.status == 'completed'

    def test_status_invalid_value_ignored(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            entry_id = entry.id

        admin_client.post(f'/schedule/entry/{entry_id}/status', data={'status': 'invalid_status'})
        with app.app_context():
            from app.models import Entry
            e = Entry.query.get(entry_id)
            assert e.status == 'waiting'  # unchanged

    def test_reorder_entry_up(self, admin_client, app):
        with app.app_context():
            from app.models import Stage
            from app import db
            stage = Stage(name='Stage E', display_order=1)
            db.session.add(stage)
            db.session.commit()
            stage_id = stage.id

            item = make_item()
            p1 = make_participant('PA', lkc_id='LA1')
            p2 = make_participant('PB', lkc_id='LA2')
            from app.models import Entry
            e1 = Entry(participant_id=p1.id, item_id=item.id,
                       stage_id=stage_id, running_order=1)
            e2 = Entry(participant_id=p2.id, item_id=item.id,
                       stage_id=stage_id, running_order=2)
            db.session.add_all([e1, e2])
            db.session.commit()
            e1_id, e2_id = e1.id, e2.id

        # Move e2 up → should swap with e1
        admin_client.post(f'/schedule/entry/{e2_id}/reorder', data={'direction': 'up'})
        with app.app_context():
            from app.models import Entry
            assert Entry.query.get(e2_id).running_order == 1
            assert Entry.query.get(e1_id).running_order == 2
