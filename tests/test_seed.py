"""
Tests for seed data — verifies all 46 competition items and their criteria
are correctly loaded from the UUKMA Kalamela Manual 2026.
"""
import pytest
from app.models import CompetitionItem, Criteria


class TestSeedData:
    def test_total_item_count(self, app_seeded):
        with app_seeded.app_context():
            count = CompetitionItem.query.count()
            assert count == 46, f'Expected 46 items, got {count}'

    def test_kids_items(self, app_seeded):
        with app_seeded.app_context():
            items = CompetitionItem.query.filter_by(category='Kids').all()
            names = {i.name for i in items}
            assert 'Solo Song (Malayalam)' in names
            assert 'Story Telling (Malayalam)' in names
            assert 'Cinematic Dance Solo' in names
            assert 'Group Cinematic Dance' in names
            assert len(items) == 4

    def test_sub_junior_items(self, app_seeded):
        with app_seeded.app_context():
            items = CompetitionItem.query.filter_by(category='Sub-Junior').all()
            assert len(items) == 11

    def test_junior_items(self, app_seeded):
        with app_seeded.app_context():
            items = CompetitionItem.query.filter_by(category='Junior').all()
            assert len(items) == 11

    def test_senior_items(self, app_seeded):
        with app_seeded.app_context():
            items = CompetitionItem.query.filter_by(category='Senior').all()
            assert len(items) == 11

    def test_super_senior_items(self, app_seeded):
        with app_seeded.app_context():
            items = CompetitionItem.query.filter_by(category='Super Senior').all()
            names = {i.name for i in items}
            assert 'Solo Song (Malayalam Light Music)' in names
            assert 'Group Cinematic Dance' in names
            assert 'Group Dance / Sanga Nritham' in names
            assert len(items) == 3

    def test_common_items(self, app_seeded):
        with app_seeded.app_context():
            items = CompetitionItem.query.filter_by(category='Common').all()
            names = {i.name for i in items}
            assert 'Mime' in names
            assert 'Group Song' in names
            assert 'Thiruvathira' in names
            assert 'Oppana' in names
            assert 'Margamkali' in names
            assert 'Naadan Pattukal (Folk Song)' in names
            assert len(items) == 6

    def test_female_only_items(self, app_seeded):
        with app_seeded.app_context():
            female_items = CompetitionItem.query.filter_by(
                gender_restriction='Female'
            ).all()
            names = {i.name for i in female_items}
            assert 'Thiruvathira' in names
            assert 'Oppana' in names
            assert 'Margamkali' in names
            assert len(female_items) == 3

    def test_group_items_have_member_limits(self, app_seeded):
        with app_seeded.app_context():
            mime = CompetitionItem.query.filter_by(name='Mime').first()
            assert mime.min_members == 4
            assert mime.max_members == 6

            group_song = CompetitionItem.query.filter_by(
                name='Group Song', category='Common'
            ).first()
            assert group_song.min_members == 3
            assert group_song.max_members == 10

    def test_all_items_have_criteria(self, app_seeded):
        with app_seeded.app_context():
            items = CompetitionItem.query.all()
            for item in items:
                assert len(item.criteria) > 0, f'{item.name} ({item.category}) has no criteria'

    def test_criteria_totals_100_per_judge(self, app_seeded):
        with app_seeded.app_context():
            items = CompetitionItem.query.all()
            for item in items:
                total = item.max_marks_per_judge
                assert total == 100, (
                    f'{item.name} ({item.category}): criteria total {total}, expected 100'
                )

    def test_solo_items_have_no_member_limits(self, app_seeded):
        with app_seeded.app_context():
            solo_items = CompetitionItem.query.filter_by(item_type='solo').all()
            for item in solo_items:
                assert item.min_members is None
                assert item.max_members is None

    def test_durations_are_set(self, app_seeded):
        with app_seeded.app_context():
            items = CompetitionItem.query.all()
            for item in items:
                assert item.max_duration_mins is not None
                assert item.max_duration_mins > 0

    def test_seed_is_idempotent(self, app_seeded):
        """Running seed_if_empty again should not duplicate items."""
        with app_seeded.app_context():
            from app.seed_data import seed_if_empty
            seed_if_empty()
            assert CompetitionItem.query.count() == 46
