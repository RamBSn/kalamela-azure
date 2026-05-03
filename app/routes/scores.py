from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app import db
from app.models import Entry, Score, Criteria, AuditLog, CompetitionItem, EventConfig


def _effective_num_judges(item):
    """Return the judge count for an item: item override or global default."""
    if item.num_judges and item.num_judges > 0:
        return item.num_judges
    cfg = EventConfig.query.first()
    return (cfg.default_num_judges if cfg and cfg.default_num_judges else 3)

scores_bp = Blueprint('scores', __name__)

@scores_bp.before_request
def require_admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=request.path))


@scores_bp.before_request
def require_admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=request.path))


@scores_bp.route('/')
def index():
    items_with_entries = db.session.query(CompetitionItem).join(Entry).distinct().order_by(
        CompetitionItem.category, CompetitionItem.name
    ).all()
    item_stats = {}
    for item in items_with_entries:
        active = [e for e in item.entries if not e.is_cancelled]
        completed = sum(1 for e in active if e.scores_complete())
        item_stats[item.id] = {
            'active': len(active),
            'completed': completed,
            'pending': len(active) - completed,
        }
    return render_template('scores/index.html', items=items_with_entries, item_stats=item_stats)


@scores_bp.route('/event/<int:item_id>')
def event_entries(item_id):
    item = CompetitionItem.query.get_or_404(item_id)
    all_entries = Entry.query.filter_by(item_id=item_id).order_by(Entry.id).all()
    judges = list(range(1, _effective_num_judges(item) + 1))
    active = [e for e in all_entries if not e.is_cancelled]
    cancelled = [e for e in all_entries if e.is_cancelled]
    completed = sum(1 for e in active if e.scores_complete())
    return render_template(
        'scores/event_entries.html',
        item=item, entries=active, cancelled_entries=cancelled,
        judges=judges,
        completed=completed, pending=len(active) - completed,
    )


@scores_bp.route('/entry/<int:entry_id>', methods=['GET', 'POST'])
def score_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    if entry.is_cancelled:
        flash(f'{entry.display_name} is withdrawn from this event.', 'warning')
        return redirect(url_for('scores.event_entries', item_id=entry.item_id))
    item = entry.competition_item
    criteria = item.criteria

    judges = list(range(1, _effective_num_judges(item) + 1))

    if request.method == 'POST':
        reason = request.form.get('edit_reason', '').strip() or None

        # Block if any active judge has all-zero scores
        all_zero_judges = []
        for judge_num in judges:
            if request.form.get(f'judge_{judge_num}_active') != '1':
                continue
            vals = [
                float((request.form.get(f'j{judge_num}_c{c.id}') or '0').strip())
                for c in criteria
            ]
            if vals and all(v == 0 for v in vals):
                all_zero_judges.append(judge_num)

        if all_zero_judges:
            names = ', '.join(f'Judge {j}' for j in all_zero_judges)
            flash(
                f'{names}: all scores are 0. Mark the judge as absent or enter actual scores.',
                'danger'
            )
            # Re-render with the submitted values so the user doesn't lose their work
            score_map = {}
            for j in judges:
                for c in criteria:
                    raw = request.form.get(f'j{j}_c{c.id}')
                    if raw is not None:
                        score_map.setdefault(j, {})[c.id] = float(raw or 0)
            active_j = {j for j in judges if request.form.get(f'judge_{j}_active') == '1'}
            return render_template(
                'scores/score_entry.html',
                entry=entry, item=item, criteria=criteria,
                score_map=score_map, judges=judges, active_judges=active_j,
            )

        for judge_num in judges:
            judge_active = request.form.get(f'judge_{judge_num}_active') == '1'
            if not judge_active:
                # Remove any existing scores for this judge
                Score.query.filter_by(
                    entry_id=entry_id, judge_number=judge_num
                ).delete()
                continue

            for c in criteria:
                field_key = f'j{judge_num}_c{c.id}'
                val_str = (request.form.get(field_key) or '0').strip()
                val = min(max(float(val_str), 0), c.max_marks)

                existing = Score.query.filter_by(
                    entry_id=entry_id, judge_number=judge_num, criteria_id=c.id
                ).first()

                if existing:
                    if existing.marks != val:
                        db.session.add(AuditLog(
                            entry_id=entry_id,
                            judge_number=judge_num,
                            criteria_id=c.id,
                            old_value=existing.marks,
                            new_value=val,
                            reason=reason,
                        ))
                        existing.marks = val
                else:
                    db.session.add(Score(
                        entry_id=entry_id,
                        judge_number=judge_num,
                        criteria_id=c.id,
                        marks=val,
                    ))

        db.session.commit()
        flash('Scores saved.', 'success')
        return redirect(url_for('scores.event_entries', item_id=item.id))

    # Build score lookup: {judge_num: {criteria_id: marks}}
    score_map = {}
    for s in entry.scores:
        score_map.setdefault(s.judge_number, {})[s.criteria_id] = s.marks

    # Judges currently active — all configured judges by default if no scores yet
    active_judges = entry.active_judges if entry.scores else set(judges)

    return render_template(
        'scores/score_entry.html',
        entry=entry,
        item=item,
        criteria=criteria,
        score_map=score_map,
        judges=judges,
        active_judges=active_judges,
    )


@scores_bp.route('/entry/<int:entry_id>/review')
def review_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    item = entry.competition_item
    criteria = item.criteria
    score_map = {}
    for s in entry.scores:
        score_map.setdefault(s.judge_number, {})[s.criteria_id] = s.marks

    audit_logs = AuditLog.query.filter_by(entry_id=entry_id).order_by(AuditLog.timestamp.desc()).all()
    return render_template(
        'scores/review.html',
        entry=entry,
        item=item,
        criteria=criteria,
        score_map=score_map,
        audit_logs=audit_logs,
    )


@scores_bp.route('/api/entry/<int:entry_id>/totals')
def entry_totals(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    return jsonify({
        'j1': entry.judge_total(1),
        'j2': entry.judge_total(2),
        'j3': entry.judge_total(3),
        'final': entry.final_score,
    })


@scores_bp.route('/entry/<int:entry_id>/cancel', methods=['POST'])
def cancel_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    entry.is_cancelled = True
    db.session.commit()
    flash(f'{entry.display_name} marked as withdrawn.', 'warning')
    return redirect(url_for('scores.event_entries', item_id=entry.item_id))


@scores_bp.route('/entry/<int:entry_id>/restore', methods=['POST'])
def restore_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    entry.is_cancelled = False
    db.session.commit()
    flash(f'{entry.display_name} restored.', 'success')
    return redirect(url_for('scores.event_entries', item_id=entry.item_id))
