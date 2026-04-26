"""
Unit tests for all SQLAlchemy models and their business logic.
"""
import pytest
from datetime import date
from app import db as _db
from app.models import (
    Participant, CompetitionItem, Criteria,
    GroupEntry, Entry, Score, AuditLog,
)
from tests.conftest import make_item, make_participant, make_entry, make_group, score_entry_fully


# ── Age Category Derivation ────────────────────────────────────────────────────

class TestDeriveCategory:
    def test_kids(self, app):
        with app.app_context():
            assert Participant.derive_category(date(2019, 1, 1)) == 'Kids'
            assert Participant.derive_category(date(2018, 9, 1)) == 'Kids'

    def test_sub_junior(self, app):
        with app.app_context():
            assert Participant.derive_category(date(2015, 3, 15)) == 'Sub-Junior'
            assert Participant.derive_category(date(2014, 9, 1)) == 'Sub-Junior'
            assert Participant.derive_category(date(2018, 8, 31)) == 'Sub-Junior'

    def test_junior(self, app):
        with app.app_context():
            assert Participant.derive_category(date(2011, 6, 1)) == 'Junior'
            assert Participant.derive_category(date(2009, 9, 1)) == 'Junior'
            assert Participant.derive_category(date(2014, 8, 31)) == 'Junior'

    def test_senior(self, app):
        with app.app_context():
            assert Participant.derive_category(date(2000, 1, 1)) == 'Senior'
            assert Participant.derive_category(date(2009, 8, 31)) == 'Senior'

    def test_super_senior(self, app):
        with app.app_context():
            assert Participant.derive_category(date(1991, 8, 31)) == 'Super Senior'
            assert Participant.derive_category(date(1980, 1, 1)) == 'Super Senior'

    def test_boundary_senior_not_super(self, app):
        with app.app_context():
            # Born 1991-09-01 = above 35 cutoff
            assert Participant.derive_category(date(1991, 9, 1)) == 'Senior'


# ── Chest Number Auto-assignment ──────────────────────────────────────────────

class TestChestNumbers:
    def test_first_participant_gets_101(self, app):
        with app.app_context():
            assert Participant.next_chest_number() == 101

    def test_increments(self, app):
        with app.app_context():
            p1 = make_participant('P1')
            assert p1.chest_number == 101
            p2 = make_participant('P2', lkc_id='LKC002')
            assert p2.chest_number == 102

    def test_group_uses_shared_counter(self, app):
        with app.app_context():
            item = make_item(item_type='group', min_m=3, max_m=8)
            p = make_participant('P1')
            assert p.chest_number == 101
            g = make_group(item=item, members=[p])
            assert g.chest_number == 102


# ── Entry Score Calculations ───────────────────────────────────────────────────

class TestEntryScores:
    def test_judge_total(self, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            criteria = item.criteria

            # Score Judge 1: 30, 25, 20 = 75
            for c, marks in zip(criteria, [30, 25, 20]):
                _db.session.add(Score(
                    entry_id=entry.id, judge_number=1,
                    criteria_id=c.id, marks=marks
                ))
            _db.session.commit()
            assert entry.judge_total(1) == 75.0
            assert entry.judge_total(2) == 0.0

    def test_final_score_is_sum_of_three_judges(self, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            # Score each criterion with exact values (no capping)
            criteria = item.criteria
            for judge, vals in [(1, [30, 25, 20]), (2, [28, 22, 18]), (3, [25, 20, 15])]:
                for c, v in zip(criteria, vals):
                    _db.session.add(Score(
                        entry_id=entry.id, judge_number=judge,
                        criteria_id=c.id, marks=v,
                    ))
            _db.session.commit()
            # J1=75, J2=68, J3=60 → final=203
            assert abs(entry.judge_total(1) - 75.0) < 0.1
            assert abs(entry.judge_total(2) - 68.0) < 0.1
            assert abs(entry.judge_total(3) - 60.0) < 0.1
            assert abs(entry.final_score - 203.0) < 0.1

    def test_scores_complete_true_when_all_judges_filled(self, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            assert not entry.scores_complete()
            score_entry_fully(entry)
            assert entry.scores_complete()

    def test_scores_complete_false_when_partial(self, app):
        """A judge with only some criteria scored = incomplete."""
        with app.app_context():
            item = make_item()  # has 3 criteria
            p = make_participant()
            entry = make_entry(p, item)
            # Only fill judge 1's FIRST criterion (partial)
            _db.session.add(Score(
                entry_id=entry.id, judge_number=1,
                criteria_id=item.criteria[0].id, marks=item.criteria[0].max_marks
            ))
            _db.session.commit()
            assert not entry.scores_complete()

    def test_scores_complete_with_two_judges(self, app):
        """Two fully-scored judges counts as complete (third absent is allowed)."""
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            for judge in [1, 2]:
                for c in item.criteria:
                    _db.session.add(Score(
                        entry_id=entry.id, judge_number=judge,
                        criteria_id=c.id, marks=c.max_marks
                    ))
            _db.session.commit()
            assert entry.scores_complete()


# ── Max Marks Per Judge ────────────────────────────────────────────────────────

class TestMaxMarks:
    def test_max_marks_sums_criteria(self, app):
        with app.app_context():
            item = make_item()  # criteria: 40+35+25 = 100
            assert item.max_marks_per_judge == 100

    def test_empty_criteria_gives_zero(self, app):
        with app.app_context():
            item = CompetitionItem(
                name='Empty', category='Common', item_type='solo',
                max_duration_mins=5, is_custom=True
            )
            _db.session.add(item)
            _db.session.commit()
            assert item.max_marks_per_judge == 0


# ── Group Entry ────────────────────────────────────────────────────────────────

class TestGroupEntry:
    def test_group_display_name(self, app):
        with app.app_context():
            item = make_item(item_type='group', min_m=3, max_m=8)
            p1 = make_participant('Alice', lkc_id='L1')
            p2 = make_participant('Bob', lkc_id='L2', dob=date(2011, 1, 1))
            group = make_group('Dance Team', item=item, members=[p1, p2])
            entry = group.entry
            assert entry.display_name == 'Dance Team'
            assert entry.chest_number == group.chest_number

    def test_group_member_count(self, app):
        with app.app_context():
            item = make_item(item_type='group', min_m=3, max_m=8)
            members = [make_participant(f'P{i}', lkc_id=f'L{i}') for i in range(4)]
            group = make_group(item=item, members=members)
            assert len(group.members) == 4


# ── Audit Log ─────────────────────────────────────────────────────────────────

class TestAuditLog:
    def test_audit_log_recorded(self, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            c = item.criteria[0]

            # Initial score
            _db.session.add(Score(
                entry_id=entry.id, judge_number=1,
                criteria_id=c.id, marks=20
            ))
            _db.session.commit()

            # Edit + audit
            score = Score.query.filter_by(
                entry_id=entry.id, judge_number=1, criteria_id=c.id
            ).first()
            old = score.marks
            _db.session.add(AuditLog(
                entry_id=entry.id, judge_number=1,
                criteria_id=c.id, old_value=old,
                new_value=25, reason='Typo fix',
            ))
            score.marks = 25
            _db.session.commit()

            log = AuditLog.query.filter_by(entry_id=entry.id).first()
            assert log.old_value == 20
            assert log.new_value == 25
            assert log.reason == 'Typo fix'
