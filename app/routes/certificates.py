import io
import os
import zipfile
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, send_file, current_app, abort, session)
from werkzeug.utils import secure_filename
from app import db
from app.models import EventConfig, CompetitionItem, Entry
from app.routes.results import get_event_results, get_all_results, \
    compute_individual_points, compute_individual_champions, \
    compute_kalathilakam_kalaprathibha, compute_bhasha_kesari

certificates_bp = Blueprint('certificates', __name__)


@certificates_bp.before_request
def require_admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=request.path))

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
POSITION_LABELS = {1: '1st Prize', 2: '2nd Prize', 3: '3rd Prize'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@certificates_bp.route('/')
def index():
    cfg = EventConfig.query.first()
    # Items with scored entries
    items = (CompetitionItem.query.join(Entry).distinct()
             .order_by(CompetitionItem.category, CompetitionItem.name).all())
    return render_template('certificates/index.html', cfg=cfg, items=items)


@certificates_bp.route('/template', methods=['GET', 'POST'])
def template_setup():
    cfg = EventConfig.query.first()
    if not cfg:
        cfg = EventConfig()
        db.session.add(cfg)
        db.session.commit()

    if request.method == 'POST':
        cfg.cert_title_text = request.form.get('cert_title_text', 'Certificate of Achievement').strip()
        cfg.cert_font_colour = request.form.get('cert_font_colour', '#1a1a2e').strip()

        # Handle background image upload
        if 'bg_image' in request.files:
            file = request.files['bg_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename('cert_background.' + file.filename.rsplit('.', 1)[1].lower())
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(upload_path)
                cfg.cert_bg_image = filename
                flash('Background image uploaded.', 'success')

        if request.form.get('remove_bg'):
            cfg.cert_bg_image = None

        db.session.commit()
        flash('Certificate template saved.', 'success')
        return redirect(url_for('certificates.template_setup'))

    return render_template('certificates/template.html', cfg=cfg)


def _make_cert(cfg, name, item_name, category, position_label):
    from app.pdf.certificate import generate_certificate
    bg_path = None
    if cfg and cfg.cert_bg_image:
        bg_path = os.path.join(current_app.config['UPLOAD_FOLDER'], cfg.cert_bg_image)

    return generate_certificate(
        event_name=cfg.event_name if cfg else 'Kalamela',
        participant_name=name,
        item_name=item_name,
        category=category,
        position=position_label,
        event_date=cfg.event_date.strftime('%d %B %Y') if cfg and cfg.event_date else '',
        bg_image_path=bg_path,
        title_text=cfg.cert_title_text if cfg else 'Certificate of Achievement',
        font_colour=cfg.cert_font_colour if cfg else '#1a1a2e',
    )


@certificates_bp.route('/event/<int:item_id>')
def event_certificates(item_id):
    """Download all certificates for an event as a ZIP."""
    item = CompetitionItem.query.get_or_404(item_id)
    cfg = EventConfig.query.first()
    ranked = get_event_results(item_id)

    if not ranked:
        flash('No scored entries for this event.', 'warning')
        return redirect(url_for('certificates.index'))

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as zf:
        for r in ranked:
            if r['position'] > 3:
                continue
            label = POSITION_LABELS[r['position']]
            name = r['entry'].display_name
            pdf = _make_cert(cfg, name, item.name, item.category, label)
            safe_name = f'{r["position"]}_{name}_{item.name}.pdf'.replace(' ', '_')
            zf.writestr(safe_name, pdf)

    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'certificates_{item.name}.zip'.replace(' ', '_'),
    )


@certificates_bp.route('/single/<int:entry_id>/<int:position>')
def single_certificate(entry_id, position):
    entry = Entry.query.get_or_404(entry_id)
    cfg = EventConfig.query.first()
    item = entry.competition_item
    label = POSITION_LABELS.get(position, f'{position}th')

    pdf = _make_cert(cfg, entry.display_name, item.name, item.category, label)
    filename = f'certificate_{entry.display_name}_{item.name}.pdf'.replace(' ', '_')
    return send_file(
        io.BytesIO(pdf),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=filename,
    )


@certificates_bp.route('/awards')
def award_certificates():
    """Generate certificates for all special award winners."""
    cfg = EventConfig.query.first()
    all_results = get_all_results()
    points_map = compute_individual_points(all_results)
    champions = compute_individual_champions(points_map)
    kk = compute_kalathilakam_kalaprathibha(all_results, points_map)
    bhasha = compute_bhasha_kesari(all_results, points_map)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as zf:
        # Individual Champions
        for cat, winners in champions.items():
            for w in winners:
                pdf = _make_cert(cfg, w['name'], 'All Events',
                                 cat, f'Individual Champion — {cat}')
                safe = f'champion_{cat}_{w["name"]}.pdf'.replace(' ', '_')
                zf.writestr(safe, pdf)

        # Kalathilakam / Kalaprathibha
        for award_name, winners in kk.items():
            for w in winners:
                pdf = _make_cert(cfg, w['name'], 'All Events',
                                 'All Categories', award_name)
                safe = f'{award_name}_{w["name"]}.pdf'.replace(' ', '_')
                zf.writestr(safe, pdf)

        # Bhasha Kesari
        for w in bhasha:
            pdf = _make_cert(cfg, w['name'], 'Language Events',
                             w['category'], 'Malayalam Bhasha Kesari Puraskaram')
            safe = f'BhashaKesari_{w["name"]}.pdf'.replace(' ', '_')
            zf.writestr(safe, pdf)

    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name='award_certificates.zip',
    )
