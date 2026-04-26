from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from app import db
from app.models import Stage, Entry, CompetitionItem, EventConfig, Participant, GroupEntry

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


@schedule_bp.route('/chest-numbers')
def chest_numbers():
    cfg = EventConfig.query.first()

    include_registered = request.args.get('registered', '1') == '1'
    range_from = request.args.get('from', type=int, default=0)
    range_to   = request.args.get('to',   type=int, default=0)

    # Build name lookup for registered numbers
    participants = {p.chest_number: p.full_name
                    for p in Participant.query.all()}
    groups = {g.chest_number: g.group_name
              for g in GroupEntry.query.all()}
    registered_numbers = sorted(set(participants) | set(groups))

    numbers = []
    if include_registered:
        for n in registered_numbers:
            numbers.append({
                'number': n,
                'name': participants.get(n) or groups.get(n, ''),
                'registered': True,
            })

    # Extra range (skip already included)
    existing = {item['number'] for item in numbers}
    if range_from and range_to and range_from <= range_to:
        for n in range(range_from, range_to + 1):
            if n not in existing:
                numbers.append({'number': n, 'name': '', 'registered': False})

    numbers.sort(key=lambda x: x['number'])

    return render_template(
        'schedule/chest_numbers.html',
        numbers=numbers,
        registered_count=len(registered_numbers),
        include_registered=include_registered,
        range_from=range_from or '',
        range_to=range_to or '',
        cfg=cfg,
    )


@schedule_bp.route('/chest-numbers/pdf')
def chest_numbers_pdf():
    include_registered = request.args.get('registered', '1') == '1'
    range_from = request.args.get('from', type=int, default=0)
    range_to   = request.args.get('to',   type=int, default=0)

    cfg = EventConfig.query.first()
    event_name = cfg.event_name if cfg else 'Kalamela'

    participants = {p.chest_number: p.full_name for p in Participant.query.all()}
    groups = {g.chest_number: g.group_name for g in GroupEntry.query.all()}
    registered_numbers = sorted(set(participants) | set(groups))

    numbers = []
    if include_registered:
        for n in registered_numbers:
            numbers.append({
                'number': n,
                'name': participants.get(n) or groups.get(n, ''),
                'registered': True,
            })

    existing = {item['number'] for item in numbers}
    if range_from and range_to and range_from <= range_to:
        for n in range(range_from, range_to + 1):
            if n not in existing:
                numbers.append({'number': n, 'name': '', 'registered': False})

    numbers.sort(key=lambda x: x['number'])

    from app.pdf.chest_numbers import generate_chest_numbers_pdf
    pdf_bytes = generate_chest_numbers_pdf(numbers, event_name)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename="chest_numbers.pdf"'
    return response


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
