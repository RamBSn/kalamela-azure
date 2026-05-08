import os
from types import SimpleNamespace
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models import EventConfig, Stage, CompetitionItem, Criteria, Entry

setup_bp = Blueprint('setup', __name__)

@setup_bp.before_request
def require_admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=request.path))


@setup_bp.route('/', methods=['GET', 'POST'])
def event_settings():
    cfg = EventConfig.query.first()
    if not cfg:
        cfg = EventConfig()
        db.session.add(cfg)
        db.session.commit()

    if request.method == 'POST':
        cfg.event_name = request.form['event_name'].strip()
        from datetime import date
        date_str = request.form.get('event_date', '').strip()
        if date_str:
            cfg.event_date = date.fromisoformat(date_str)
        else:
            cfg.event_date = None
        cfg.venue = request.form.get('venue', '').strip()
        cfg.scoresheet_blank_rows = int(request.form.get('scoresheet_blank_rows', 3))
        cfg.default_num_judges = int(request.form.get('default_num_judges', 3))
        cfg.welcome_tagline = request.form.get('welcome_tagline', '').strip() or None

        # Logo upload
        if request.form.get('remove_logo'):
            cfg.welcome_logo = None
        elif 'welcome_logo' in request.files:
            f = request.files['welcome_logo']
            if f and f.filename:
                ext = f.filename.rsplit('.', 1)[-1].lower()
                if ext in {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}:
                    filename = secure_filename(f'welcome_logo.{ext}')
                    f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                    cfg.welcome_logo = filename

        # SMTP settings
        cfg.smtp_host       = request.form.get('smtp_host', '').strip() or None
        cfg.smtp_port       = int(request.form.get('smtp_port') or 587)
        cfg.smtp_username   = request.form.get('smtp_username', '').strip() or None
        smtp_pw = request.form.get('smtp_password', '').strip()
        if smtp_pw:                        # only overwrite if a new value was typed
            cfg.smtp_password = smtp_pw
        cfg.smtp_from_name  = request.form.get('smtp_from_name', '').strip() or None
        cfg.smtp_from_email = request.form.get('smtp_from_email', '').strip() or None
        cfg.smtp_use_tls    = bool(request.form.get('smtp_use_tls'))

        db.session.commit()
        flash('Event settings saved.', 'success')
        return redirect(url_for('setup.event_settings'))

    return render_template('setup/event_settings.html', cfg=cfg)


# ── Stages ────────────────────────────────────────────────────────────────────

@setup_bp.route('/stages', methods=['GET', 'POST'])
def stages():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            max_order = db.session.query(db.func.max(Stage.display_order)).scalar() or 0
            db.session.add(Stage(name=name, display_order=max_order + 1))
            db.session.commit()
            flash(f'Stage "{name}" added.', 'success')
        return redirect(url_for('setup.stages'))

    all_stages = Stage.query.order_by(Stage.display_order).all()

    # Items that have at least one unassigned entry
    items_with_unassigned = (
        CompetitionItem.query
        .join(Entry, Entry.item_id == CompetitionItem.id)
        .filter(Entry.stage_id == None)
        .distinct()
        .order_by(CompetitionItem.category, CompetitionItem.name)
        .all()
    )

    # Per-stage: unique items present in that stage's entries
    stage_items = {}
    stage_item_ids = {}
    for stage in all_stages:
        seen = {}
        for e in stage.entries:
            if e.item_id not in seen:
                seen[e.item_id] = e.competition_item
        stage_items[stage.id] = sorted(seen.values(), key=lambda i: (i.category, i.name))
        stage_item_ids[stage.id] = list(seen.keys())

    # Items available to assign per stage (unassigned items not already in that stage)
    stage_available_items = {
        stage.id: [i for i in items_with_unassigned if i.id not in stage_item_ids[stage.id]]
        for stage in all_stages
    }

    return render_template('setup/stages.html', stages=all_stages,
                           stage_items=stage_items,
                           stage_available_items=stage_available_items)


@setup_bp.route('/stages/<int:stage_id>/delete', methods=['POST'])
def delete_stage(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    db.session.delete(stage)
    db.session.commit()
    flash(f'Stage "{stage.name}" deleted.', 'success')
    return redirect(url_for('setup.stages'))


@setup_bp.route('/stages/<int:stage_id>/edit', methods=['POST'])
def edit_stage(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    stage.name = request.form['name'].strip()
    db.session.commit()
    flash('Stage updated.', 'success')
    return redirect(url_for('setup.stages'))


@setup_bp.route('/stages/<int:stage_id>/assign-items', methods=['POST'])
def assign_items_to_stage(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    item_ids = [int(i) for i in request.form.getlist('item_ids[]') if i]

    last = db.session.query(db.func.max(Entry.running_order)).filter_by(
        stage_id=stage_id).scalar() or 0

    assigned = 0
    for item_id in item_ids:
        unassigned = Entry.query.filter_by(item_id=item_id, stage_id=None).order_by(Entry.id).all()
        for e in unassigned:
            last += 1
            e.stage_id = stage_id
            e.running_order = last
            assigned += 1

    db.session.commit()
    if assigned:
        flash(f'{assigned} entr{"y" if assigned == 1 else "ies"} assigned to {stage.name}.', 'success')
    else:
        flash('No unassigned entries found for the selected items.', 'warning')
    return redirect(url_for('setup.stages'))


@setup_bp.route('/stages/<int:stage_id>/remove-item', methods=['POST'])
def remove_item_from_stage(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    item_id = int(request.form['item_id'])
    entries = Entry.query.filter_by(item_id=item_id, stage_id=stage_id).all()
    for e in entries:
        e.stage_id = None
        e.running_order = None
    db.session.commit()
    item = CompetitionItem.query.get(item_id)
    flash(f'"{item.name}" removed from {stage.name}.', 'success')
    return redirect(url_for('setup.stages'))


# ── Competition Items ─────────────────────────────────────────────────────────

CATEGORIES = ['Kids', 'Sub-Junior', 'Junior', 'Senior', 'Super Senior', 'Common']


@setup_bp.route('/items')
def items():
    all_items = CompetitionItem.query.order_by(
        CompetitionItem.category, CompetitionItem.name
    ).all()
    return render_template('setup/items.html', items=all_items, categories=CATEGORIES)


def _form_item_namespace():
    """Build a SimpleNamespace from POST data to repopulate the form on error."""
    return SimpleNamespace(
        name=request.form.get('name', '').strip(),
        category=request.form.get('category', ''),
        item_type=request.form.get('item_type', 'solo'),
        max_duration_mins=request.form.get('max_duration_mins') or None,
        min_members=request.form.get('min_members') or None,
        max_members=request.form.get('max_members') or None,
        gender_restriction=request.form.get('gender_restriction') or None,
        num_judges=int(request.form.get('num_judges', 3)),
        criteria=[],
    )


@setup_bp.route('/items/add', methods=['GET', 'POST'])
def add_item():
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category']

        if CompetitionItem.query.filter_by(name=name, category=category).first():
            flash(f'"{name}" already exists in the {category} category.', 'danger')
            return render_template('setup/item_form.html',
                                   item=_form_item_namespace(), categories=CATEGORIES)

        item = CompetitionItem(
            name=name,
            category=category,
            item_type=request.form['item_type'],
            max_duration_mins=int(request.form['max_duration_mins']) if request.form.get('max_duration_mins') else None,
            min_members=int(request.form['min_members']) if request.form.get('min_members') else None,
            max_members=int(request.form['max_members']) if request.form.get('max_members') else None,
            gender_restriction=request.form.get('gender_restriction') or None,
            num_judges=int(request.form.get('num_judges', 3)),
            is_custom=True,
        )
        db.session.add(item)
        db.session.flush()

        # Add criteria from form
        criteria_names = request.form.getlist('criteria_name[]')
        criteria_max = request.form.getlist('criteria_max[]')
        for order, (cname, cmax) in enumerate(zip(criteria_names, criteria_max)):
            cname = cname.strip()
            if cname and cmax:
                db.session.add(Criteria(
                    item_id=item.id,
                    name=cname,
                    max_marks=int(cmax),
                    display_order=order,
                ))
        db.session.commit()
        flash(f'Item "{item.name}" added.', 'success')
        return redirect(url_for('setup.items'))

    return render_template('setup/item_form.html', item=None, categories=CATEGORIES)


@setup_bp.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_item(item_id):
    item = CompetitionItem.query.get_or_404(item_id)
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category']

        duplicate = CompetitionItem.query.filter_by(name=name, category=category).filter(
            CompetitionItem.id != item_id
        ).first()
        if duplicate:
            flash(f'"{name}" already exists in the {category} category.', 'danger')
            return render_template('setup/item_form.html', item=item, categories=CATEGORIES)

        item.name = name
        item.category = category
        item.item_type = request.form['item_type']
        item.max_duration_mins = int(request.form['max_duration_mins']) if request.form.get('max_duration_mins') else None
        item.min_members = int(request.form['min_members']) if request.form.get('min_members') else None
        item.max_members = int(request.form['max_members']) if request.form.get('max_members') else None
        item.gender_restriction = request.form.get('gender_restriction') or None
        item.num_judges = int(request.form.get('num_judges', 3))

        # Replace criteria
        for c in item.criteria:
            db.session.delete(c)
        db.session.flush()

        criteria_names = request.form.getlist('criteria_name[]')
        criteria_max = request.form.getlist('criteria_max[]')
        for order, (cname, cmax) in enumerate(zip(criteria_names, criteria_max)):
            cname = cname.strip()
            if cname and cmax:
                db.session.add(Criteria(
                    item_id=item.id,
                    name=cname,
                    max_marks=int(cmax),
                    display_order=order,
                ))
        db.session.commit()
        flash(f'Item "{item.name}" updated.', 'success')
        return redirect(url_for('setup.items'))

    return render_template('setup/item_form.html', item=item, categories=CATEGORIES)


@setup_bp.route('/items/<int:item_id>/delete', methods=['POST'])
def delete_item(item_id):
    item = CompetitionItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f'Item "{name}" deleted.', 'success')
    return redirect(url_for('setup.items'))
