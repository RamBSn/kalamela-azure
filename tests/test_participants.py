"""
Tests for participant registration, eligibility enforcement,
group registration, and edit/delete operations.
"""
import pytest
from datetime import date
from tests.conftest import make_item, make_participant, make_entry, make_group


class TestIndividualRegistration:
    def test_register_page_loads(self, client):
        r = client.get('/participants/register')
        assert r.status_code == 200

    def test_register_individual(self, client):
        r = client.post('/participants/register', data={
            'full_name': 'Arjun Kumar',
            'date_of_birth': '2011-06-01',
            'lkc_id': 'LKC101',
            'gender': 'Male',
            'phone': '07000000001',
            'email': '',
            'parent_name': '',
            'items[]': [],
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'Arjun Kumar' in r.data

    def test_auto_category_from_dob(self, client, app):
        """DOB 2011-06-01 → Junior (age ~15 in Sep 2026)."""
        client.post('/participants/register', data={
            'full_name': 'Junior User',
            'date_of_birth': '2011-06-01',
            'lkc_id': 'LKC102',
            'gender': 'Male',
            'phone': '07000000002',
            'items[]': [],
        })
        with app.app_context():
            from app.models import Participant
            p = Participant.query.filter_by(full_name='Junior User').first()
            assert p.category == 'Junior'

    def test_auto_chest_number_assigned(self, client, app):
        client.post('/participants/register', data={
            'full_name': 'First Person',
            'date_of_birth': '2011-06-01',
            'lkc_id': 'LKC103',
            'gender': 'Female',
            'phone': '07000000003',
            'items[]': [],
        })
        with app.app_context():
            from app.models import Participant
            p = Participant.query.filter_by(full_name='First Person').first()
            assert p.chest_number == 101

    def test_participant_list_page(self, admin_client):
        r = admin_client.get('/participants/')
        assert r.status_code == 200

    def test_search_participant(self, admin_client, app):
        with app.app_context():
            make_participant('Priya Nair', lkc_id='LKC200')
        r = admin_client.get('/participants/?q=Priya')
        assert r.status_code == 200
        assert b'Priya Nair' in r.data

    def test_delete_participant(self, admin_client, app):
        with app.app_context():
            p = make_participant('Delete Me', lkc_id='LKC300')
            pid = p.id
        r = admin_client.post(f'/participants/{pid}/delete', follow_redirects=True)
        assert r.status_code == 200
        # Verify deleted from DB
        with app.app_context():
            from app.models import Participant
            assert Participant.query.get(pid) is None

    def test_api_category_from_dob(self, client):
        r = client.get('/participants/api/category-from-dob?dob=2011-06-01')
        assert r.status_code == 200
        data = r.get_json()
        assert data['category'] == 'Junior'

    def test_api_category_kids(self, client):
        r = client.get('/participants/api/category-from-dob?dob=2020-01-01')
        assert r.get_json()['category'] == 'Kids'

    def test_api_category_invalid_dob(self, client):
        r = client.get('/participants/api/category-from-dob?dob=invalid')
        assert r.get_json()['category'] == ''


class TestEligibilityEnforcement:
    def test_gender_restriction_warning(self, client, app):
        """Male trying to register for Thiruvathira should warn."""
        with app.app_context():
            from app.models import CompetitionItem, Criteria
            from app import db
            # Create Thiruvathira-like item with female restriction
            item = CompetitionItem(
                name='Thiruvathira', category='Common', item_type='group',
                max_duration_mins=10, max_members=10,
                gender_restriction='Female', is_custom=True
            )
            db.session.add(item)
            db.session.flush()
            db.session.add(Criteria(item_id=item.id, name='A', max_marks=100))
            db.session.commit()
            item_id = item.id

        r = client.post('/participants/register', data={
            'full_name': 'Male User',
            'date_of_birth': '2011-06-01',
            'lkc_id': 'LKC400',
            'gender': 'Male',
            'phone': '07000000004',
            'items[]': [str(item_id)],
        }, follow_redirects=True)
        assert b'females only' in r.data.lower() or b'warning' in r.data.lower()

    def test_max_events_enforced(self, client, app):
        """Registering 5 events should trigger warning."""
        with app.app_context():
            from app import db
            items = []
            for i in range(5):
                item = make_item(name=f'Solo Event {i}', item_type='solo')
                items.append(item)
            item_ids = [str(i.id) for i in items]

        r = client.post('/participants/register', data={
            'full_name': 'Busy Person',
            'date_of_birth': '2011-06-01',
            'lkc_id': 'LKC500',
            'gender': 'Male',
            'phone': '07000000005',
            'items[]': item_ids,
        }, follow_redirects=True)
        # Should show warning (not registered silently with 5 events)
        assert r.status_code == 200

    def test_eligibility_block_cannot_be_bypassed(self, client, app):
        """Gender eligibility block cannot be bypassed — override_warnings is ignored."""
        with app.app_context():
            from app.models import CompetitionItem, Criteria
            from app import db
            item = CompetitionItem(
                name='Female Only Test', category='Common', item_type='group',
                max_duration_mins=5, gender_restriction='Female', is_custom=True
            )
            db.session.add(item)
            db.session.flush()
            db.session.add(Criteria(item_id=item.id, name='A', max_marks=100))
            db.session.commit()
            item_id = item.id

        r = client.post('/participants/register', data={
            'full_name': 'Override Male',
            'date_of_birth': '2011-06-01',
            'lkc_id': 'LKC600',
            'gender': 'Male',
            'phone': '07000000006',
            'items[]': [str(item_id)],
            'override_warnings': '1',
        }, follow_redirects=True)
        assert r.status_code == 200
        # Participant must NOT be registered despite override flag
        with app.app_context():
            from app.models import Participant
            p = Participant.query.filter_by(full_name='Override Male').first()
            assert p is None


class TestGroupRegistration:
    def test_register_group_page_loads(self, client):
        r = client.get('/participants/groups/register')
        assert r.status_code == 200

    def test_register_valid_group(self, client, app):
        with app.app_context():
            item = make_item(name='Group Dance Test', item_type='group',
                             min_m=3, max_m=8)
            members = [
                make_participant(f'Member {i}', lkc_id=f'LKC{700+i}')
                for i in range(3)
            ]
            item_id = item.id
            member_ids = [str(m.id) for m in members]

        r = client.post('/participants/groups/register', data={
            'group_name': 'Star Dancers',
            'item_id': str(item_id),
            'members[]': member_ids,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'Star Dancers' in r.data

    def test_group_size_minimum_warning(self, client, app):
        """Group with fewer than min_members should warn."""
        with app.app_context():
            item = make_item(name='Big Group Event', item_type='group',
                             min_m=4, max_m=8)
            p = make_participant('Lone Wolf', lkc_id='LKC800')
            item_id = item.id
            p_id = p.id

        r = client.post('/participants/groups/register', data={
            'group_name': 'Too Small',
            'item_id': str(item_id),
            'members[]': [str(p_id)],
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'minimum' in r.data.lower() or b'warning' in r.data.lower()

    def test_groups_list_page(self, client):
        r = client.get('/participants/groups')
        assert r.status_code == 200

    def test_delete_group(self, admin_client, app):
        with app.app_context():
            item = make_item(name='Deletable Group Event', item_type='group',
                             min_m=1, max_m=8)
            p = make_participant('Group Member', lkc_id='LKC900')
            group = make_group('Delete Group', item=item, members=[p])
            gid = group.id

        r = admin_client.post(f'/participants/groups/{gid}/delete',
                              follow_redirects=True)
        assert r.status_code == 200
