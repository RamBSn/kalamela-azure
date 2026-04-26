"""
Tests for authentication: login, logout, access control.
Public routes are accessible without login.
Admin routes redirect to /auth/login when not authenticated.
"""
import pytest
from tests.conftest import make_participant, make_item


class TestLoginLogout:
    def test_login_page_loads(self, client):
        r = client.get('/auth/login')
        assert r.status_code == 200
        assert b'password' in r.data.lower()
        assert b'Login' in r.data

    def test_login_correct_password(self, client):
        r = client.post('/auth/login', data={'password': 'password'},
                        follow_redirects=True)
        assert r.status_code == 200
        with client.session_transaction() as sess:
            assert sess.get('admin_logged_in') is True

    def test_login_wrong_password(self, client):
        r = client.post('/auth/login', data={'password': 'wrong'},
                        follow_redirects=True)
        assert r.status_code == 200
        assert b'Incorrect password' in r.data
        with client.session_transaction() as sess:
            assert not sess.get('admin_logged_in')

    def test_login_empty_password(self, client):
        r = client.post('/auth/login', data={'password': ''},
                        follow_redirects=True)
        assert r.status_code == 200
        with client.session_transaction() as sess:
            assert not sess.get('admin_logged_in')

    def test_logout_clears_session(self, admin_client):
        r = admin_client.get('/auth/logout', follow_redirects=True)
        assert r.status_code == 200
        with admin_client.session_transaction() as sess:
            assert not sess.get('admin_logged_in')

    def test_login_redirects_to_next(self, client):
        r = client.post('/auth/login',
                        data={'password': 'password', 'next': '/setup/'},
                        follow_redirects=False)
        assert r.status_code == 302
        assert '/setup/' in r.headers['Location']

    def test_already_logged_in_redirects_from_login(self, admin_client):
        r = admin_client.get('/auth/login', follow_redirects=False)
        assert r.status_code == 302


class TestPublicAccess:
    """These routes must be accessible without any login."""

    def test_dashboard_public(self, client):
        r = client.get('/')
        assert r.status_code == 200

    def test_participant_list_requires_login(self, client):
        r = client.get('/participants/', follow_redirects=False)
        assert r.status_code == 302
        assert '/auth/login' in r.headers['Location']

    def test_participant_list_accessible_as_admin(self, admin_client):
        r = admin_client.get('/participants/')
        assert r.status_code == 200

    def test_register_individual_get_public(self, client):
        r = client.get('/participants/register')
        assert r.status_code == 200

    def test_register_individual_post_public(self, client):
        r = client.post('/participants/register', data={
            'full_name': 'Public Registrant',
            'date_of_birth': '2011-06-01',
            'lkc_id': 'PUB001',
            'gender': 'Male',
            'phone': '07000000099',
            'items[]': [],
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_register_group_public(self, client):
        r = client.get('/participants/groups/register')
        assert r.status_code == 200

    def test_groups_list_public(self, client):
        r = client.get('/participants/groups')
        assert r.status_code == 200

    def test_category_api_public(self, client):
        r = client.get('/participants/api/category-from-dob?dob=2011-06-01')
        assert r.status_code == 200

    def test_results_index_public(self, client):
        r = client.get('/results/')
        assert r.status_code == 200

    def test_results_live_public(self, client, app):
        with app.app_context():
            item = make_item()
            item_id = item.id
        r = client.get(f'/results/live/{item_id}')
        assert r.status_code == 200


class TestAdminRequired:
    """These routes must redirect to login when not authenticated."""

    def _assert_redirects_to_login(self, response):
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

    def test_setup_requires_login(self, client):
        self._assert_redirects_to_login(client.get('/setup/'))

    def test_stages_requires_login(self, client):
        self._assert_redirects_to_login(client.get('/setup/stages'))

    def test_items_requires_login(self, client):
        self._assert_redirects_to_login(client.get('/setup/items'))

    def test_schedule_requires_login(self, client):
        self._assert_redirects_to_login(client.get('/schedule/'))

    def test_scores_requires_login(self, client):
        self._assert_redirects_to_login(client.get('/scores/'))

    def test_certificates_requires_login(self, client):
        self._assert_redirects_to_login(client.get('/certificates/'))

    def test_scoresheets_requires_login(self, client):
        self._assert_redirects_to_login(client.get('/scoresheets/'))

    def test_data_requires_login(self, client):
        self._assert_redirects_to_login(client.get('/data/'))

    def test_participant_edit_requires_login(self, client, app):
        with app.app_context():
            p = make_participant('Edit Target', lkc_id='ET001')
            pid = p.id
        self._assert_redirects_to_login(client.get(f'/participants/{pid}/edit'))

    def test_participant_delete_requires_login(self, client, app):
        with app.app_context():
            p = make_participant('Delete Target', lkc_id='DT001')
            pid = p.id
        self._assert_redirects_to_login(
            client.post(f'/participants/{pid}/delete'))

    def test_group_delete_requires_login(self, client, app):
        with app.app_context():
            item = make_item(item_type='group', min_m=1, max_m=8)
            p = make_participant('GM', lkc_id='GM001')
            from tests.conftest import make_group
            g = make_group(item=item, members=[p])
            gid = g.id
        self._assert_redirects_to_login(
            client.post(f'/participants/groups/{gid}/delete'))


class TestChangePassword:
    def test_change_password_page_loads(self, admin_client):
        r = admin_client.get('/auth/change-password')
        assert r.status_code == 200
        assert b'Current Password' in r.data

    def test_change_password_requires_login(self, client):
        r = client.get('/auth/change-password', follow_redirects=False)
        assert r.status_code == 302
        assert '/auth/login' in r.headers['Location']

    def test_change_password_success(self, admin_client):
        r = admin_client.post('/auth/change-password', data={
            'current_password': 'password',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'Password changed successfully' in r.data

    def test_change_password_wrong_current(self, admin_client):
        r = admin_client.post('/auth/change-password', data={
            'current_password': 'wrongpassword',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'Current password is incorrect' in r.data

    def test_change_password_mismatch_confirm(self, admin_client):
        r = admin_client.post('/auth/change-password', data={
            'current_password': 'password',
            'new_password': 'newpass123',
            'confirm_password': 'different',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'do not match' in r.data

    def test_change_password_empty_new_password(self, admin_client):
        r = admin_client.post('/auth/change-password', data={
            'current_password': 'password',
            'new_password': '',
            'confirm_password': '',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'cannot be empty' in r.data

    def test_new_password_takes_effect(self, admin_client):
        """After changing password, must log out and use the new password."""
        admin_client.post('/auth/change-password', data={
            'current_password': 'password',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123',
        })
        # Log out so the session is cleared
        admin_client.get('/auth/logout')

        # Old password should now fail
        r = admin_client.post('/auth/login', data={'password': 'password'},
                              follow_redirects=True)
        assert b'Incorrect password' in r.data

        # New password should succeed
        admin_client.post('/auth/login', data={'password': 'newpass123'})
        with admin_client.session_transaction() as sess:
            assert sess.get('admin_logged_in') is True


class TestAdminAccess:
    """Admin-only routes must be accessible when logged in."""

    def test_setup_accessible_as_admin(self, admin_client):
        r = admin_client.get('/setup/')
        assert r.status_code == 200

    def test_schedule_accessible_as_admin(self, admin_client):
        r = admin_client.get('/schedule/')
        assert r.status_code == 200

    def test_scores_accessible_as_admin(self, admin_client):
        r = admin_client.get('/scores/')
        assert r.status_code == 200

    def test_data_accessible_as_admin(self, admin_client):
        r = admin_client.get('/data/')
        assert r.status_code == 200

    def test_certificates_accessible_as_admin(self, admin_client):
        r = admin_client.get('/certificates/')
        assert r.status_code == 200

    def test_scoresheets_accessible_as_admin(self, admin_client):
        r = admin_client.get('/scoresheets/')
        assert r.status_code == 200
