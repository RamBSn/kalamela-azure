"""
Tests for score entry, auto-totals, max enforcement, and audit trail.
"""
import pytest
from tests.conftest import make_item, make_participant, make_entry, score_entry_fully


class TestScoreEntry:
    def test_scores_index_loads(self, admin_client):
        r = admin_client.get('/scores/')
        assert r.status_code == 200

    def test_score_entry_page_loads(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            entry_id = entry.id

        r = admin_client.get(f'/scores/entry/{entry_id}')
        assert r.status_code == 200
        assert b'Judge 1' in r.data
        assert b'Judge 2' in r.data
        assert b'Judge 3' in r.data

    def test_event_entries_page_loads(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            make_entry(p, item)
            item_id = item.id

        r = admin_client.get(f'/scores/event/{item_id}')
        assert r.status_code == 200

    def test_enter_scores_saves_correctly(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            criteria = item.criteria
            entry_id = entry.id
            c0_id, c1_id, c2_id = criteria[0].id, criteria[1].id, criteria[2].id

        form_data = {
            'judge_1_active': '1', 'judge_2_active': '1', 'judge_3_active': '1',
            f'j1_c{c0_id}': '35', f'j1_c{c1_id}': '30', f'j1_c{c2_id}': '20',
            f'j2_c{c0_id}': '32', f'j2_c{c1_id}': '28', f'j2_c{c2_id}': '18',
            f'j3_c{c0_id}': '30', f'j3_c{c1_id}': '25', f'j3_c{c2_id}': '15',
        }
        r = admin_client.post(f'/scores/entry/{entry_id}', data=form_data,
                        follow_redirects=True)
        assert r.status_code == 200

        with app.app_context():
            from app.models import Entry
            e = Entry.query.get(entry_id)
            assert abs(e.judge_total(1) - 85.0) < 0.1
            assert abs(e.judge_total(2) - 78.0) < 0.1
            assert abs(e.judge_total(3) - 70.0) < 0.1
            assert abs(e.final_score - 233.0) < 0.1
            assert e.scores_complete()

    def test_score_capped_at_max(self, admin_client, app):
        """Marks exceeding max should be capped at max."""
        with app.app_context():
            item = make_item()  # criteria: 40, 35, 25
            p = make_participant()
            entry = make_entry(p, item)
            criteria = item.criteria
            entry_id = entry.id
            c0_id = criteria[0].id  # max 40
            c1_id = criteria[1].id  # max 35
            c2_id = criteria[2].id  # max 25

        # Try to submit 999 for first criterion (max=40)
        form_data = {
            'judge_1_active': '1', 'judge_2_active': '1', 'judge_3_active': '1',
            f'j1_c{c0_id}': '999', f'j1_c{c1_id}': '35', f'j1_c{c2_id}': '25',
            f'j2_c{c0_id}': '40', f'j2_c{c1_id}': '35', f'j2_c{c2_id}': '25',
            f'j3_c{c0_id}': '40', f'j3_c{c1_id}': '35', f'j3_c{c2_id}': '25',
        }
        admin_client.post(f'/scores/entry/{entry_id}', data=form_data)
        with app.app_context():
            from app.models import Score
            s = Score.query.filter_by(
                entry_id=entry_id, judge_number=1, criteria_id=c0_id
            ).first()
            assert s.marks == 40  # capped

    def test_edit_score_creates_audit_log(self, admin_client, app):
        """Editing a score should create an AuditLog entry."""
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            criteria = item.criteria
            entry_id = entry.id
            c0_id, c1_id, c2_id = criteria[0].id, criteria[1].id, criteria[2].id

        # First, enter initial scores
        form_data = {
            'judge_1_active': '1', 'judge_2_active': '1', 'judge_3_active': '1',
            f'j1_c{c0_id}': '30', f'j1_c{c1_id}': '25', f'j1_c{c2_id}': '20',
            f'j2_c{c0_id}': '30', f'j2_c{c1_id}': '25', f'j2_c{c2_id}': '20',
            f'j3_c{c0_id}': '30', f'j3_c{c1_id}': '25', f'j3_c{c2_id}': '20',
        }
        admin_client.post(f'/scores/entry/{entry_id}', data=form_data)

        # Edit with a different value + reason
        edit_data = dict(form_data)
        edit_data[f'j1_c{c0_id}'] = '35'  # was 30
        edit_data['edit_reason'] = 'Typo correction'
        admin_client.post(f'/scores/entry/{entry_id}', data=edit_data)

        with app.app_context():
            from app.models import AuditLog
            log = AuditLog.query.filter_by(entry_id=entry_id).first()
            assert log is not None
            assert log.old_value == 30
            assert log.new_value == 35
            assert log.reason == 'Typo correction'
            assert log.judge_number == 1

    def test_review_page_loads(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            entry_id = entry.id

        r = admin_client.get(f'/scores/entry/{entry_id}/review')
        assert r.status_code == 200

    def test_entry_totals_api(self, admin_client, app):
        with app.app_context():
            from app.models import Score as S
            from app import db
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            # Score with exact values: J1=75, J2=68, J3=60 → total=203
            criteria = item.criteria
            for judge, vals in [(1, [30, 25, 20]), (2, [28, 22, 18]), (3, [25, 20, 15])]:
                for c, v in zip(criteria, vals):
                    db.session.add(S(entry_id=entry.id, judge_number=judge,
                                     criteria_id=c.id, marks=v))
            db.session.commit()
            entry_id = entry.id

        r = admin_client.get(f'/scores/api/entry/{entry_id}/totals')
        assert r.status_code == 200
        data = r.get_json()
        assert 'j1' in data and 'j2' in data and 'j3' in data and 'final' in data
        assert abs(data['j1'] - 75.0) < 0.1
        assert abs(data['final'] - 203.0) < 0.1

    def test_scores_index_shows_completion_status(self, admin_client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            score_entry_fully(entry)

        r = admin_client.get('/scores/')
        assert r.status_code == 200
        assert b'All done' in r.data  # all entries scored
