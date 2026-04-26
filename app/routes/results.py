from collections import defaultdict
from flask import Blueprint, render_template, request
from app import db
from app.models import Entry, CompetitionItem, Participant, GroupEntry

results_bp = Blueprint('results', __name__)

CATEGORIES = ['Kids', 'Sub-Junior', 'Junior', 'Senior', 'Super Senior', 'Common']
POINTS = {1: 5, 2: 3, 3: 1}
GROUP_POINTS = {1: 1.0, 2: 0.5, 3: 0.25}

# Items that count as Dance (single) for Kalathilakam/Kalaprathibha
DANCE_ITEMS = {
    'Bharathanatyam', 'Mohiniyattom', 'Folk Dance', 'Cinematic Dance Solo',
    'Classical Dance Solo', 'Cinematic Dance',
}


def get_event_results(item_id):
    """Return ranked entries for an item. Ties share the same position."""
    entries = Entry.query.filter_by(item_id=item_id).all()
    complete = [e for e in entries if not e.is_cancelled and e.scores_complete()]
    if not complete:
        return []

    sorted_entries = sorted(complete, key=lambda e: e.final_score, reverse=True)
    ranked = []
    rank = 1
    i = 0
    while i < len(sorted_entries):
        score = sorted_entries[i].final_score
        tied = [e for e in sorted_entries if e.final_score == score]
        for e in tied:
            ranked.append({'entry': e, 'position': rank, 'score': score})
        rank += len(tied)
        i += len(tied)

    return ranked


def get_all_results():
    """Return {item_id: [ranked dicts]} for all items with complete scores."""
    items = CompetitionItem.query.all()
    all_results = {}
    for item in items:
        ranked = get_event_results(item.id)
        if ranked:
            all_results[item.id] = ranked
    return all_results


def compute_individual_points(all_results):
    """
    Returns {participant_id: {'solo': float, 'group': float, 'total': float,
                              'category': str, 'name': str, 'gender': str,
                              'results': [(item_name, position, points, type)]}}
    """
    points_map = defaultdict(lambda: {
        'solo': 0.0, 'group': 0.0, 'total': 0.0,
        'category': '', 'name': '', 'gender': '', 'results': []
    })

    for item_id, ranked in all_results.items():
        item = CompetitionItem.query.get(item_id)
        for r in ranked:
            pos = r['position']
            if pos > 3:
                continue
            entry = r['entry']

            if item.item_type == 'solo':
                pts = POINTS.get(pos, 0)
                pid = entry.participant_id
                if pid:
                    p = entry.participant
                    points_map[pid]['solo'] += pts
                    points_map[pid]['total'] += pts
                    points_map[pid]['category'] = p.category
                    points_map[pid]['name'] = p.full_name
                    points_map[pid]['gender'] = p.gender
                    points_map[pid]['results'].append(
                        (item.name, pos, pts, 'solo', item.category)
                    )
            else:
                pts = GROUP_POINTS.get(pos, 0)
                gid = entry.group_id
                if gid:
                    group = entry.group_entry
                    for member in group.members:
                        points_map[member.id]['group'] += pts
                        points_map[member.id]['total'] += pts
                        points_map[member.id]['category'] = member.category
                        points_map[member.id]['name'] = member.full_name
                        points_map[member.id]['gender'] = member.gender
                        points_map[member.id]['results'].append(
                            (item.name, pos, pts, 'group', item.category)
                        )

    return points_map


def compute_individual_champions(points_map):
    """Return {category: [champion dicts]} — highest solo points per category."""
    by_category = defaultdict(list)
    for pid, data in points_map.items():
        cat = data['category']
        if cat and cat != 'Common':
            by_category[cat].append({'pid': pid, **data})

    champions = {}
    for cat, players in by_category.items():
        max_solo = max(p['solo'] for p in players)
        winners = [p for p in players if p['solo'] == max_solo]
        # Tiebreaker: group points
        if len(winners) > 1:
            max_group = max(p['group'] for p in winners)
            winners = [p for p in winners if p['group'] == max_group]
        champions[cat] = winners
    return champions


def compute_kalathilakam_kalaprathibha(all_results, points_map):
    """
    Kalathilakam (Female) / Kalaprathibha (Male):
    Eligibility: must have 1st in a Dance single AND a Non-Dance single.
    Fallback: 1st or 2nd in both types.
    Tiebreaker: group points.
    """
    results = {'Kalathilakam': [], 'Kalaprathibha': []}

    for gender, award_name in [('Female', 'Kalathilakam'), ('Male', 'Kalaprathibha')]:
        candidates = {
            pid: data for pid, data in points_map.items()
            if data['gender'] == gender
        }

        def qualifies(pid, min_pos=1):
            has_dance = any(
                r[0] in DANCE_ITEMS and r[1] <= min_pos and r[3] == 'solo'
                for r in candidates[pid]['results']
            )
            has_non_dance = any(
                r[0] not in DANCE_ITEMS and r[1] <= min_pos and r[3] == 'solo'
                for r in candidates[pid]['results']
            )
            return has_dance and has_non_dance

        eligible = [pid for pid in candidates if qualifies(pid, min_pos=1)]
        if not eligible:
            eligible = [pid for pid in candidates if qualifies(pid, min_pos=2)]

        if not eligible:
            results[award_name] = []
            continue

        max_solo = max(candidates[pid]['solo'] for pid in eligible)
        winners = [pid for pid in eligible if candidates[pid]['solo'] == max_solo]
        if len(winners) > 1:
            max_group = max(candidates[pid]['group'] for pid in winners)
            winners = [pid for pid in winners if candidates[pid]['group'] == max_group]

        results[award_name] = [{'pid': pid, **candidates[pid]} for pid in winners]

    return results


BHASHA_KESARI_ITEMS = {
    'Elocution (Malayalam)', 'Poem Recitation (Malayalam)',
    'Monoact (Malayalam)', 'Story Telling (Malayalam)',
}


def compute_bhasha_kesari(all_results, points_map):
    """Most points across Malayalam language events (all categories)."""
    lang_points = defaultdict(float)
    lang_results = defaultdict(list)

    for item_id, ranked in all_results.items():
        item = CompetitionItem.query.get(item_id)
        if item.name not in BHASHA_KESARI_ITEMS:
            continue
        for r in ranked:
            pos = r['position']
            if pos > 3:
                continue
            entry = r['entry']
            if entry.participant_id:
                pts = POINTS.get(pos, 0)
                lang_points[entry.participant_id] += pts
                lang_results[entry.participant_id].append(
                    (item.name, pos, pts, item.category)
                )

    if not lang_points:
        return []

    max_pts = max(lang_points.values())
    winners = []
    for pid, pts in lang_points.items():
        if pts == max_pts:
            p = Participant.query.get(pid)
            winners.append({
                'pid': pid, 'name': p.full_name, 'gender': p.gender,
                'category': p.category, 'points': pts,
                'results': lang_results[pid],
            })
    return winners


@results_bp.route('/')
def index():
    all_results = get_all_results()
    points_map = compute_individual_points(all_results)
    champions = compute_individual_champions(points_map)
    kk = compute_kalathilakam_kalaprathibha(all_results, points_map)
    bhasha = compute_bhasha_kesari(all_results, points_map)

    # Event results list for selector
    items_with_results = [
        CompetitionItem.query.get(iid) for iid in all_results
    ]

    return render_template(
        'results/index.html',
        champions=champions,
        kk=kk,
        bhasha=bhasha,
        items_with_results=items_with_results,
        categories=CATEGORIES,
    )


@results_bp.route('/event/<int:item_id>')
def event_results(item_id):
    item = CompetitionItem.query.get_or_404(item_id)
    ranked = get_event_results(item_id)
    all_entries = Entry.query.filter_by(item_id=item_id).all()
    return render_template(
        'results/event.html',
        item=item,
        ranked=ranked,
        all_entries=all_entries,
    )


@results_bp.route('/live/<int:item_id>')
def live(item_id):
    """Auto-refreshing live leaderboard."""
    item = CompetitionItem.query.get_or_404(item_id)
    ranked = get_event_results(item_id)
    all_entries = Entry.query.filter_by(item_id=item_id).all()
    return render_template(
        'results/live.html',
        item=item,
        ranked=ranked,
        all_entries=all_entries,
    )
