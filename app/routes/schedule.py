from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Stage, Entry, CompetitionItem, EventConfig

schedule_bp = Blueprint('schedule', __name__)


@schedule_bp.before_request
def require_admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=request.path))


@schedule_bp.route('/')
def index():
    stages = Stage.query.order_by(Stage.display_order).all()
    unassigned = Entry.query.filter_by(stage_id=None).order_by(Entry.id).all()
    return render_template('schedule/index.html', stages=stages, unassigned=unassigned)


@schedule_bp.route('/assign', methods=['POST'])
def assign():
    entry_id = int(request.form['entry_id'])
    stage_id = request.form.get('stage_id')
    entry = Entry.query.get_or_404(entry_id)
    if stage_id:
        entry.stage_id = int(stage_id)
        # Set running order at end of stage
        last = db.session.query(db.func.max(Entry.running_order)).filter_by(
            stage_id=int(stage_id)
        ).scalar() or 0
        entry.running_order = last + 1
    else:
        entry.stage_id = None
        entry.running_order = None
    db.session.commit()
    flash('Stage assignment updated.', 'success')
    return redirect(url_for('schedule.index'))


@schedule_bp.route('/stage/<int:stage_id>')
def stage_view(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    entries = Entry.query.filter_by(stage_id=stage_id).order_by(Entry.running_order).all()
    return render_template('schedule/stage.html', stage=stage, entries=entries)


@schedule_bp.route('/entry/<int:entry_id>/status', methods=['POST'])
def update_status(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    new_status = request.form['status']
    if new_status in ('waiting', 'performing', 'completed'):
        entry.status = new_status
        db.session.commit()
    return redirect(request.referrer or url_for('schedule.index'))


@schedule_bp.route('/print')
def print_schedule():
    category = request.args.get('category', '')
    categories = ['Kids', 'Sub-Junior', 'Junior', 'Senior', 'Super Senior', 'Common']
    stages = Stage.query.order_by(Stage.display_order).all()
    cfg = EventConfig.query.first()

    schedule_data = []
    for stage in stages:
        entries = Entry.query.filter_by(stage_id=stage.id).order_by(Entry.running_order).all()
        if category:
            entries = [e for e in entries if e.competition_item.category == category]
        if entries:
            schedule_data.append({'stage': stage, 'entries': entries})

    return render_template('schedule/print.html',
                           schedule_data=schedule_data,
                           category=category,
                           categories=categories,
                           cfg=cfg)


@schedule_bp.route('/entry/<int:entry_id>/reorder', methods=['POST'])
def reorder(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    direction = request.form.get('direction')
    if not entry.stage_id:
        return redirect(url_for('schedule.index'))

    siblings = Entry.query.filter_by(stage_id=entry.stage_id).order_by(Entry.running_order).all()
    idx = next((i for i, e in enumerate(siblings) if e.id == entry_id), None)
    if idx is None:
        return redirect(url_for('schedule.stage_view', stage_id=entry.stage_id))

    if direction == 'up' and idx > 0:
        siblings[idx].running_order, siblings[idx - 1].running_order = (
            siblings[idx - 1].running_order, siblings[idx].running_order
        )
    elif direction == 'down' and idx < len(siblings) - 1:
        siblings[idx].running_order, siblings[idx + 1].running_order = (
            siblings[idx + 1].running_order, siblings[idx].running_order
        )
    db.session.commit()
    return redirect(url_for('schedule.stage_view', stage_id=entry.stage_id))
