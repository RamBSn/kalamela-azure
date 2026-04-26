"""
Shared pytest fixtures for all test modules.
Uses a temp-file SQLite database — isolated per test function.
"""
import os
import tempfile
import pytest
from datetime import date
from app import create_app, db as _db
from app.models import (
    EventConfig, Stage, CompetitionItem, Criteria,
    Participant, GroupEntry, Entry, Score,
)


@pytest.fixture(scope='function')
def app():
    """Flask app with isolated temp SQLite file, no seed data."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    backup_dir = tempfile.mkdtemp()

    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
        'BACKUP_FOLDER': backup_dir,
        'SERVER_NAME': 'localhost',
    }
    test_app = create_app(test_config=test_config)

    with test_app.app_context():
        # DB already created by create_app → seed_if_empty ran
        # Ensure exactly one EventConfig with test data
        EventConfig.query.delete()
        _db.session.add(EventConfig(
            event_name='Test Kalamela 2026',
            event_date=date(2026, 5, 1),
            venue='Test Hall',
        ))
        _db.session.commit()
        yield test_app
        _db.session.remove()
        _db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='function')
def app_seeded(app):
    """App fixture — seed data already loaded by create_app via seed_if_empty."""
    return app


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


@pytest.fixture(scope='function')
def admin_client(client):
    """Authenticated admin test client — session flag set directly."""
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    return client


@pytest.fixture(scope='function')
def client_seeded(app_seeded):
    return app_seeded.test_client()


@pytest.fixture(scope='function')
def admin_client_seeded(client_seeded):
    with client_seeded.session_transaction() as sess:
        sess['admin_logged_in'] = True
    return client_seeded


# ── Domain object factories ────────────────────────────────────────────────────

def make_item(name='Folk Dance', category='Junior', item_type='solo',
              duration=7, min_m=None, max_m=None, gender=None):
    item = CompetitionItem(
        name=name, category=category, item_type=item_type,
        max_duration_mins=duration, min_members=min_m, max_members=max_m,
        gender_restriction=gender, is_custom=True,
    )
    _db.session.add(item)
    _db.session.flush()
    # Three criteria totalling exactly 100
    for order, (cname, cmax) in enumerate([('Criteria A', 40), ('Criteria B', 35), ('Criteria C', 25)]):
        _db.session.add(Criteria(
            item_id=item.id, name=cname, max_marks=cmax, display_order=order
        ))
    _db.session.commit()
    return item


def make_participant(name='Test User', dob=date(2010, 6, 1),
                     gender='Male', lkc_id='LKC001',
                     phone='07000000000'):
    p = Participant(
        chest_number=Participant.next_chest_number(),
        full_name=name,
        date_of_birth=dob,
        category=Participant.derive_category(dob),
        lkc_id=lkc_id,
        gender=gender,
        phone=phone,
    )
    _db.session.add(p)
    _db.session.commit()
    return p


def make_entry(participant, item):
    e = Entry(participant_id=participant.id, item_id=item.id)
    _db.session.add(e)
    _db.session.commit()
    return e


def make_group(name='Test Group', item=None, members=None):
    group = GroupEntry(
        group_name=name,
        item_id=item.id,
        chest_number=GroupEntry.next_chest_number(),
    )
    group.members = members or []
    _db.session.add(group)
    _db.session.flush()
    entry = Entry(group_id=group.id, item_id=item.id)
    _db.session.add(entry)
    _db.session.commit()
    return group


def score_entry_fully(entry, j1=80, j2=75, j3=70):
    """
    Fill all 3 judges' scores for an entry.
    Assigns marks proportionally to criteria weights, capped at max.
    The actual totals per judge may differ slightly from j1/j2/j3 if
    individual criteria caps are hit.
    """
    criteria = entry.competition_item.criteria
    total_max = sum(c.max_marks for c in criteria)

    for judge, desired_total in [(1, j1), (2, j2), (3, j3)]:
        for c in criteria:
            # Proportional allocation, capped at max
            proportion = c.max_marks / total_max
            marks = min(round(desired_total * proportion, 1), c.max_marks)
            existing = Score.query.filter_by(
                entry_id=entry.id, judge_number=judge, criteria_id=c.id
            ).first()
            if existing:
                existing.marks = marks
            else:
                _db.session.add(Score(
                    entry_id=entry.id, judge_number=judge,
                    criteria_id=c.id, marks=marks,
                ))
    _db.session.commit()


def exact_judge_total(entry, judge_number):
    """Return the actual sum of scores for a judge (after proportional allocation)."""
    return sum(
        s.marks for s in Score.query.filter_by(
            entry_id=entry.id, judge_number=judge_number
        ).all()
    )
