from flask import Blueprint, render_template, send_file, abort, session, redirect, url_for, request
import io
from app.models import CompetitionItem, Entry, EventConfig
from app.pdf.scoresheet import _entry_gender


def _effective_num_judges(item):
    if item.num_judges and item.num_judges > 0:
        return item.num_judges
    cfg = EventConfig.query.first()
    return (cfg.default_num_judges if cfg and cfg.default_num_judges else 3)

scoresheets_bp = Blueprint('scoresheets', __name__)


@scoresheets_bp.before_request
def require_admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=request.path))


@scoresheets_bp.route('/')
def index():
    # Only show items that have at least one entry
    items = (
        CompetitionItem.query
        .join(Entry)
        .distinct()
        .order_by(CompetitionItem.category, CompetitionItem.name)
        .all()
    )
    # Group by category
    from collections import defaultdict
    by_cat = defaultdict(list)
    for item in items:
        by_cat[item.category].append(item)

    cat_order = ['Kids', 'Sub-Junior', 'Junior', 'Senior', 'Super Senior', 'Common']
    grouped = [(cat, by_cat[cat]) for cat in cat_order if cat in by_cat]

    # Determine which genders are present per item
    item_genders = {}
    for item in items:
        genders = {_entry_gender(e) for e in item.entries} - {None}
        item_genders[item.id] = genders

    return render_template('scoresheets/index.html', grouped=grouped, item_genders=item_genders)


@scoresheets_bp.route('/generate/<int:item_id>')
def generate(item_id):
    item = CompetitionItem.query.get_or_404(item_id)
    gender = request.args.get('gender', '') or None  # 'Male', 'Female', or None
    n_judges = _effective_num_judges(item)
    try:
        from app.pdf.scoresheet import generate_scoresheet
        pdf_bytes = generate_scoresheet(item_id, gender=gender, num_judges=n_judges)
    except Exception as e:
        abort(500, description=str(e))

    gender_part = f'_{gender}' if gender else ''
    filename = f'scoresheet_{item.category}_{item.name}{gender_part}.pdf'.replace(' ', '_')
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=filename,
    )
