from datetime import datetime
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, make_response)
from app import db
from app.models import Stage, StagePlanItem, Entry, EventConfig, CompetitionItem

planning_bp = Blueprint('planning', __name__)

@planning_bp.before_request
def require_admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=request.path))

CATEGORY_ORDER = ['Kids', 'Sub-Junior', 'Junior', 'Senior', 'Super Senior', 'Common']


@planning_bp.before_request
def require_admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=request.path))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sync_plan(stage_id):
    """Ensure StagePlanItem rows exist for every CompetitionItem.
    Adds any items not yet in the plan; never auto-removes (user removes manually)."""
    existing_ids = {
        p.item_id for p in StagePlanItem.query.filter_by(stage_id=stage_id).all()
    }
    all_items = (CompetitionItem.query
                 .order_by(CompetitionItem.category, CompetitionItem.name)
                 .all())

    max_order = (
        db.session.query(db.func.max(StagePlanItem.display_order))
        .filter(StagePlanItem.stage_id == stage_id)
        .scalar() or 0
    )
    for item in all_items:
        if item.id not in existing_ids:
            max_order += 1
            db.session.add(StagePlanItem(
                stage_id=stage_id, item_id=item.id, display_order=max_order
            ))
    db.session.commit()


def _plan_data(stage_id):
    """Return ordered list of dicts used by both HTML and PDF views."""
    plan_items = (StagePlanItem.query
                  .filter_by(stage_id=stage_id)
                  .order_by(StagePlanItem.display_order)
                  .all())

    rows = []
    for seq, pi in enumerate(plan_items, start=1):
        entries = (Entry.query
                   .filter_by(stage_id=stage_id, item_id=pi.item_id, is_cancelled=False)
                   .order_by(Entry.running_order)
                   .all())
        rows.append({
            'plan_item': pi,
            'seq':       seq,
            'item':      pi.item,
            'entries':   entries,
        })
    return rows


# ── Routes ────────────────────────────────────────────────────────────────────

@planning_bp.route('/')
def index():
    stages = Stage.query.order_by(Stage.display_order).all()
    cfg = EventConfig.query.first()

    stage_summaries = []
    for stage in stages:
        active_entries = [e for e in stage.entries if not e.is_cancelled]
        item_ids = {e.item_id for e in active_entries}
        stage_summaries.append({
            'stage':      stage,
            'item_count': len(item_ids),
            'entry_count': len(active_entries),
        })

    return render_template('planning/index.html',
                           stage_summaries=stage_summaries, cfg=cfg)


@planning_bp.route('/stage/<int:stage_id>')
def stage_plan(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    _sync_plan(stage_id)
    cfg = EventConfig.query.first()
    plan_data = _plan_data(stage_id)
    return render_template('planning/stage.html',
                           stage=stage, plan_data=plan_data, cfg=cfg)


@planning_bp.route('/stage/<int:stage_id>/reorder', methods=['POST'])
def reorder_item(stage_id):
    plan_item_id = int(request.form['plan_item_id'])
    direction = request.form['direction']

    siblings = (StagePlanItem.query
                .filter_by(stage_id=stage_id)
                .order_by(StagePlanItem.display_order)
                .all())
    idx = next((i for i, p in enumerate(siblings) if p.id == plan_item_id), None)
    if idx is not None:
        if direction == 'up' and idx > 0:
            siblings[idx].display_order, siblings[idx - 1].display_order = (
                siblings[idx - 1].display_order, siblings[idx].display_order)
        elif direction == 'down' and idx < len(siblings) - 1:
            siblings[idx].display_order, siblings[idx + 1].display_order = (
                siblings[idx + 1].display_order, siblings[idx].display_order)
        db.session.commit()
    return redirect(url_for('planning.stage_plan', stage_id=stage_id))


@planning_bp.route('/stage/<int:stage_id>/sort-by-category', methods=['POST'])
def sort_by_category(stage_id):
    """Re-order all plan items for this stage by the standard category order."""
    plan_items = (StagePlanItem.query
                  .filter_by(stage_id=stage_id)
                  .all())

    def _cat_key(pi):
        try:
            return CATEGORY_ORDER.index(pi.item.category)
        except ValueError:
            return len(CATEGORY_ORDER)

    sorted_items = sorted(plan_items, key=_cat_key)
    for order, pi in enumerate(sorted_items, start=1):
        pi.display_order = order
    db.session.commit()
    flash('Events sorted by standard category order.', 'success')
    return redirect(url_for('planning.stage_plan', stage_id=stage_id))


@planning_bp.route('/stage/<int:stage_id>/remove', methods=['POST'])
def remove_item(stage_id):
    plan_item_id = int(request.form['plan_item_id'])
    plan_item = StagePlanItem.query.get_or_404(plan_item_id)
    db.session.delete(plan_item)
    db.session.commit()
    return redirect(url_for('planning.stage_plan', stage_id=stage_id))


@planning_bp.route('/stage/<int:stage_id>/restore-all', methods=['POST'])
def restore_all(stage_id):
    """Re-add all competition items that were manually removed."""
    _sync_plan(stage_id)
    flash('All events restored to this stage plan.', 'success')
    return redirect(url_for('planning.stage_plan', stage_id=stage_id))


@planning_bp.route('/stage/<int:stage_id>/print')
def print_plan(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    _sync_plan(stage_id)
    cfg = EventConfig.query.first()
    plan_data = _plan_data(stage_id)
    return render_template('planning/print.html',
                           stage=stage, plan_data=plan_data, cfg=cfg,
                           now=datetime.now().strftime('%d %b %Y %H:%M'))


@planning_bp.route('/stage/<int:stage_id>/pdf')
def pdf_plan(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    _sync_plan(stage_id)
    cfg = EventConfig.query.first()
    plan_data = _plan_data(stage_id)
    event_name = cfg.event_name if cfg else 'Kalamela'
    event_date = cfg.event_date.strftime('%d %B %Y') if cfg and cfg.event_date else ''

    from app.pdf.planning import generate_plan_pdf
    pdf_bytes = generate_plan_pdf(stage, plan_data, event_name, event_date)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    safe_name = stage.name.replace(' ', '_')
    response.headers['Content-Disposition'] = (
        f'inline; filename="plan_{safe_name}.pdf"'
    )
    return response
