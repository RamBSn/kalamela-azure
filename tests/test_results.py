"""
Tests for results calculation:
- Event ranking and tie handling
- Individual Champion per category
- Kalathilakam / Kalaprathibha
- Malayalam Bhasha Kesari
- Live leaderboard route
"""
import pytest
from datetime import date
from tests.conftest import (
    make_item, make_participant, make_entry, score_entry_fully
)
from app import db
from app.models import Participant, Entry, Score, Criteria, CompetitionItem


def fully_score(entry, j1, j2, j3):
    """Score an entry with exact per-judge totals, split evenly across criteria."""
    criteria = entry.competition_item.criteria
    for judge, total in [(1, j1), (2, j2), (3, j3)]:
        per = total / len(criteria)
        for c in criteria:
            marks = min(per, c.max_marks)
            existing = Score.query.filter_by(
                entry_id=entry.id, judge_number=judge, criteria_id=c.id
            ).first()
            if existing:
                existing.marks = marks
            else:
                db.session.add(Score(
                    entry_id=entry.id, judge_number=judge,
                    criteria_id=c.id, marks=marks
                ))
    db.session.commit()


class TestEventResults:
    def test_results_index_loads(self, client):
        r = client.get('/results/')
        assert r.status_code == 200

    def test_event_results_page_loads(self, client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            entry = make_entry(p, item)
            item_id = item.id

        r = client.get(f'/results/event/{item_id}')
        assert r.status_code == 200

    def test_live_leaderboard_page_loads(self, client, app):
        with app.app_context():
            item = make_item()
            p = make_participant()
            make_entry(p, item)
            item_id = item.id

        r = client.get(f'/results/live/{item_id}')
        assert r.status_code == 200

    def test_ranking_highest_score_first(self, app):
        with app.app_context():
            from app.routes.results import get_event_results
            item = make_item()
            p1 = make_participant('High Scorer', lkc_id='L1')
            p2 = make_participant('Low Scorer', lkc_id='L2')
            e1 = make_entry(p1, item)
            e2 = make_entry(p2, item)
            fully_score(e1, 90, 85, 80)  # total=255
            fully_score(e2, 70, 65, 60)  # total=195

            ranked = get_event_results(item.id)
            assert len(ranked) == 2
            assert ranked[0]['entry'].participant.full_name == 'High Scorer'
            assert ranked[0]['position'] == 1
            assert ranked[1]['position'] == 2

    def test_tie_gives_same_position(self, app):
        with app.app_context():
            from app.routes.results import get_event_results
            item = make_item()
            p1 = make_participant('Tied A', lkc_id='LA')
            p2 = make_participant('Tied B', lkc_id='LB')
            e1 = make_entry(p1, item)
            e2 = make_entry(p2, item)
            fully_score(e1, 80, 80, 80)  # total=240
            fully_score(e2, 80, 80, 80)  # total=240

            ranked = get_event_results(item.id)
            positions = [r['position'] for r in ranked]
            assert all(p == 1 for p in positions)

    def test_incomplete_entries_excluded_from_results(self, app):
        with app.app_context():
            from app.routes.results import get_event_results
            item = make_item()
            p1 = make_participant('Complete', lkc_id='LC')
            p2 = make_participant('Incomplete', lkc_id='LI')
            e1 = make_entry(p1, item)
            e2 = make_entry(p2, item)
            fully_score(e1, 80, 75, 70)
            # e2 not scored

            ranked = get_event_results(item.id)
            assert len(ranked) == 1
            assert ranked[0]['entry'].participant.full_name == 'Complete'

    def test_no_results_when_no_scores(self, app):
        with app.app_context():
            from app.routes.results import get_event_results
            item = make_item()
            p = make_participant()
            make_entry(p, item)
            assert get_event_results(item.id) == []


class TestIndividualChampion:
    def test_champion_is_highest_solo_points(self, app):
        with app.app_context():
            from app.routes.results import (
                get_all_results, compute_individual_points,
                compute_individual_champions
            )
            item1 = make_item('Solo Song Test', category='Junior',
                               item_type='solo')
            item2 = make_item('Folk Dance Test', category='Junior',
                               item_type='solo')

            p1 = make_participant('Champion', lkc_id='LC1',
                                   dob=date(2011, 1, 1))
            p2 = make_participant('Runner', lkc_id='LC2',
                                   dob=date(2011, 6, 1))

            e1 = make_entry(p1, item1)
            e2 = make_entry(p2, item1)
            e3 = make_entry(p1, item2)

            fully_score(e1, 90, 85, 80)   # p1 wins item1 (1st=5pts)
            fully_score(e2, 70, 65, 60)   # p2 second (2nd=3pts? wait...1 entry may be enough)
            fully_score(e3, 85, 80, 75)   # p1 also wins item2

            all_results = get_all_results()
            points = compute_individual_points(all_results)
            champions = compute_individual_champions(points)

            junior_champs = champions.get('Junior', [])
            assert len(junior_champs) > 0
            champ_names = [c['name'] for c in junior_champs]
            assert 'Champion' in champ_names


class TestKalathilakamKalaprathibha:
    def _setup_dance_and_nondance(self, app, gender='Female'):
        """Create a participant who wins a Dance and a Non-Dance event."""
        with app.app_context():
            # Dance item
            dance = make_item('Bharathanatyam', category='Junior',
                               item_type='solo')
            # Non-dance item
            non_dance = make_item('Elocution (Malayalam)', category='Junior',
                                   item_type='solo')

            p = make_participant('Versatile', lkc_id='KK1',
                                  gender=gender, dob=date(2011, 1, 1))
            rival = make_participant('Rival', lkc_id='KK2',
                                      gender=gender, dob=date(2011, 6, 1))

            e_dance = make_entry(p, dance)
            e_dance_rival = make_entry(rival, dance)
            e_non = make_entry(p, non_dance)

            fully_score(e_dance, 90, 85, 80)
            fully_score(e_dance_rival, 70, 65, 60)
            fully_score(e_non, 88, 83, 78)

            return dance.id, non_dance.id, p.id

    def test_kalathilakam_female_winner(self, app):
        with app.app_context():
            from app.routes.results import (
                get_all_results, compute_individual_points,
                compute_kalathilakam_kalaprathibha
            )
            self._setup_dance_and_nondance(app, gender='Female')

            all_results = get_all_results()
            points = compute_individual_points(all_results)
            kk = compute_kalathilakam_kalaprathibha(all_results, points)

            winners = kk.get('Kalathilakam', [])
            assert len(winners) > 0
            assert winners[0]['name'] == 'Versatile'

    def test_kalaprathibha_male_winner(self, app):
        with app.app_context():
            from app.routes.results import (
                get_all_results, compute_individual_points,
                compute_kalathilakam_kalaprathibha
            )
            self._setup_dance_and_nondance(app, gender='Male')

            all_results = get_all_results()
            points = compute_individual_points(all_results)
            kk = compute_kalathilakam_kalaprathibha(all_results, points)

            winners = kk.get('Kalaprathibha', [])
            assert len(winners) > 0
            assert winners[0]['name'] == 'Versatile'

    def test_no_winner_when_no_eligible_candidates(self, app):
        with app.app_context():
            from app.routes.results import (
                get_all_results, compute_individual_points,
                compute_kalathilakam_kalaprathibha
            )
            # Only a dance event, no non-dance
            item = make_item('Bharathanatyam Only', category='Junior',
                              item_type='solo')
            p = make_participant('Only Dancer', lkc_id='OD1',
                                  gender='Female', dob=date(2011, 1, 1))
            e = make_entry(p, item)
            fully_score(e, 90, 85, 80)

            all_results = get_all_results()
            points = compute_individual_points(all_results)
            kk = compute_kalathilakam_kalaprathibha(all_results, points)
            assert kk['Kalathilakam'] == []


class TestBhashaKesari:
    def test_bhasha_kesari_winner(self, app):
        with app.app_context():
            from app.routes.results import (
                get_all_results, compute_individual_points,
                compute_bhasha_kesari
            )
            # Malayalam language items
            elocution = make_item('Elocution (Malayalam)', category='Junior',
                                   item_type='solo')
            monoact = make_item('Monoact (Malayalam)', category='Junior',
                                 item_type='solo')

            p1 = make_participant('Bhasha Winner', lkc_id='BK1',
                                   dob=date(2011, 1, 1))
            p2 = make_participant('Bhasha Rival', lkc_id='BK2',
                                   dob=date(2011, 6, 1))

            e1 = make_entry(p1, elocution)
            e2 = make_entry(p2, elocution)
            e3 = make_entry(p1, monoact)

            fully_score(e1, 90, 85, 80)   # p1 wins
            fully_score(e2, 70, 65, 60)   # p2 second
            fully_score(e3, 88, 83, 78)   # p1 wins

            all_results = get_all_results()
            points = compute_individual_points(all_results)
            bhasha = compute_bhasha_kesari(all_results, points)

            assert len(bhasha) > 0
            assert bhasha[0]['name'] == 'Bhasha Winner'
            # 1st in two events = 5+5 = 10pts
            assert bhasha[0]['points'] == 10.0

    def test_bhasha_kesari_empty_when_no_language_events(self, app):
        with app.app_context():
            from app.routes.results import (
                get_all_results, compute_individual_points,
                compute_bhasha_kesari
            )
            item = make_item('Folk Dance', category='Junior', item_type='solo')
            p = make_participant()
            e = make_entry(p, item)
            fully_score(e, 90, 85, 80)

            all_results = get_all_results()
            points = compute_individual_points(all_results)
            bhasha = compute_bhasha_kesari(all_results, points)
            assert bhasha == []
