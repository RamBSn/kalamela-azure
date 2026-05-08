import io
import os
import smtplib
import zipfile
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, send_file, current_app, session)
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
POSITION_SOCIAL  = {1: 'Winner',   2: 'Runner Up', 3: 'Second Runner Up'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@certificates_bp.route('/')
def index():
    cfg   = EventConfig.query.first()
    items = (CompetitionItem.query.join(Entry).distinct()
             .order_by(CompetitionItem.category, CompetitionItem.name).all())

    item_ranked = {}
    for item in items:
        ranked = get_event_results(item.id)
        item_ranked[item.id] = [r for r in ranked if r['position'] <= 3]

    smtp_ok = bool(cfg and cfg.smtp_host and cfg.smtp_username and cfg.smtp_from_email)
    return render_template('certificates/index.html', cfg=cfg, items=items,
                           item_ranked=item_ranked, smtp_ok=smtp_ok)


# ── PDF Certificate Template ─────────────────────────────────────────────────

@certificates_bp.route('/template', methods=['GET', 'POST'])
def template_setup():
    from app.pdf.fonts import get_font_choices
    cfg = EventConfig.query.first()
    if not cfg:
        cfg = EventConfig()
        db.session.add(cfg)
        db.session.commit()

    if request.method == 'POST':
        cfg.cert_title_text     = request.form.get('cert_title_text', 'Certificate of Achievement').strip()
        cfg.cert_font_colour    = request.form.get('cert_font_colour',    '#1a1a2e').strip()
        cfg.cert_heading_colour = request.form.get('cert_heading_colour', '#8b6914').strip()
        cfg.cert_title_colour   = request.form.get('cert_title_colour',   '#1a1a2e').strip()
        cfg.cert_name_colour    = request.form.get('cert_name_colour',    '#8b6914').strip()
        cfg.cert_font           = request.form.get('cert_font', 'Times-Roman') or 'Times-Roman'

        def _save_upload(field, dest_filename):
            f = request.files.get(field)
            if f and f.filename and allowed_file(f.filename):
                ext  = f.filename.rsplit('.', 1)[1].lower()
                name = secure_filename(f'{dest_filename}.{ext}')
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], name))
                return name
            return None

        saved_bg = _save_upload('bg_image', 'cert_background')
        if saved_bg:
            cfg.cert_bg_image = saved_bg
            flash('Background image uploaded.', 'success')
        if request.form.get('remove_bg'):
            cfg.cert_bg_image = None

        saved_logo = _save_upload('cert_logo', 'cert_logo')
        if saved_logo:
            cfg.cert_logo = saved_logo
            flash('Certificate logo uploaded.', 'success')
        if request.form.get('remove_cert_logo'):
            cfg.cert_logo = None

        db.session.commit()
        flash('Certificate template saved.', 'success')
        return redirect(url_for('certificates.template_setup'))

    font_choices = get_font_choices()
    return render_template('certificates/template.html', cfg=cfg, font_choices=font_choices)


# ── Social Certificate Template ───────────────────────────────────────────────

@certificates_bp.route('/social-template', methods=['GET', 'POST'])
def social_template():
    from app.pdf.fonts import get_font_choices
    cfg = EventConfig.query.first()
    if not cfg:
        cfg = EventConfig()
        db.session.add(cfg)
        db.session.commit()

    if request.method == 'POST':
        cfg.social_cert_font        = request.form.get('social_cert_font', '') or None
        cfg.social_cert_pos_colour  = request.form.get('social_cert_pos_colour',  '#d4af37').strip()
        cfg.social_cert_name_colour = request.form.get('social_cert_name_colour', '#ffffff').strip()
        cfg.social_cert_item_colour = request.form.get('social_cert_item_colour', '#ffffff').strip()
        cfg.social_cert_evt_colour  = request.form.get('social_cert_evt_colour',  '#d4af37').strip()
        cfg.social_cert_overlay     = max(0, min(255, int(request.form.get('social_cert_overlay') or 170)))
        cfg.social_cert_footer      = request.form.get('social_cert_footer', '').strip() or None

        if 'social_bg_image' in request.files:
            file = request.files['social_bg_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename('social_background.' + file.filename.rsplit('.', 1)[1].lower())
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                cfg.social_cert_bg_image = filename
                flash('Social background image uploaded.', 'success')

        if request.form.get('remove_social_bg'):
            cfg.social_cert_bg_image = None

        db.session.commit()
        flash('Social certificate template saved.', 'success')
        return redirect(url_for('certificates.social_template'))

    font_choices = get_font_choices()
    return render_template('certificates/social_template.html', cfg=cfg, font_choices=font_choices)


def _cert_logo_path(cfg):
    """
    Resolve the best available logo for certificates.
    Priority: cert_logo (template setup) → welcome_logo (event settings) → static lkc-logo.jpeg
    """
    upload = current_app.config['UPLOAD_FOLDER']
    static_logo = os.path.join(current_app.root_path, 'static', 'lkc-logo.jpeg')
    if cfg and cfg.cert_logo:
        p = os.path.join(upload, cfg.cert_logo)
        if os.path.exists(p):
            return p
    if cfg and cfg.welcome_logo:
        p = os.path.join(upload, cfg.welcome_logo)
        if os.path.exists(p):
            return p
    if os.path.exists(static_logo):
        return static_logo
    return None


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
        heading_colour=cfg.cert_heading_colour if cfg else '#8b6914',
        title_colour=cfg.cert_title_colour if cfg else '#1a1a2e',
        name_colour=cfg.cert_name_colour if cfg else '#8b6914',
        cert_font=cfg.cert_font if cfg else None,
        cert_logo_path=_cert_logo_path(cfg),
    )


def _make_social_cert(cfg, entry, position):
    from app.pdf.social_certificate import generate_social_certificate
    # Social background: dedicated → PDF cert background → none
    bg_path = None
    if cfg and cfg.social_cert_bg_image:
        bg_path = os.path.join(current_app.config['UPLOAD_FOLDER'], cfg.social_cert_bg_image)
    elif cfg and cfg.cert_bg_image:
        bg_path = os.path.join(current_app.config['UPLOAD_FOLDER'], cfg.cert_bg_image)

    return generate_social_certificate(
        event_name=cfg.event_name if cfg else 'Kalamela',
        participant_name=entry.display_name,
        item_name=entry.competition_item.name,
        category=entry.competition_item.category,
        position=position,
        logo_path=_cert_logo_path(cfg),
        bg_image_path=bg_path,
        font_value=cfg.social_cert_font if cfg else None,
        pos_colour=cfg.social_cert_pos_colour  if cfg else '#d4af37',
        name_colour=cfg.social_cert_name_colour if cfg else '#ffffff',
        item_colour=cfg.social_cert_item_colour if cfg else '#ffffff',
        evt_colour=cfg.social_cert_evt_colour   if cfg else '#d4af37',
        overlay_opacity=cfg.social_cert_overlay if cfg else 170,
        footer_text=cfg.social_cert_footer if cfg else None,
    )


@certificates_bp.route('/event/<int:item_id>')
def event_certificates(item_id):
    item   = CompetitionItem.query.get_or_404(item_id)
    cfg    = EventConfig.query.first()
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
            name  = r['entry'].display_name
            pdf   = _make_cert(cfg, name, item.name, item.category, label)
            safe  = f'{r["position"]}_{name}_{item.name}.pdf'.replace(' ', '_')
            zf.writestr(safe, pdf)

    zip_buf.seek(0)
    return send_file(zip_buf, mimetype='application/zip', as_attachment=True,
                     download_name=f'certificates_{item.name}.zip'.replace(' ', '_'))


@certificates_bp.route('/single/<int:entry_id>/<int:position>')
def single_certificate(entry_id, position):
    entry = Entry.query.get_or_404(entry_id)
    cfg   = EventConfig.query.first()
    item  = entry.competition_item
    label = POSITION_LABELS.get(position, f'{position}th')

    pdf      = _make_cert(cfg, entry.display_name, item.name, item.category, label)
    filename = f'certificate_{entry.display_name}_{item.name}.pdf'.replace(' ', '_')
    return send_file(io.BytesIO(pdf), mimetype='application/pdf',
                     as_attachment=False, download_name=filename)


# ── Social Certificate (PNG) ──────────────────────────────────────────────────

@certificates_bp.route('/social/<int:entry_id>/<int:position>')
def social_certificate(entry_id, position):
    entry = Entry.query.get_or_404(entry_id)
    cfg   = EventConfig.query.first()
    png   = _make_social_cert(cfg, entry, position)
    name  = entry.display_name.replace(' ', '_')
    item  = entry.competition_item.name.replace(' ', '_')
    return send_file(io.BytesIO(png), mimetype='image/png', as_attachment=True,
                     download_name=f'social_{name}_{item}_{position}.png')


@certificates_bp.route('/social/email/<int:entry_id>/<int:position>', methods=['POST'])
def email_social_certificate(entry_id, position):
    entry     = Entry.query.get_or_404(entry_id)
    cfg       = EventConfig.query.first()
    recipient = entry.participant.email if entry.participant else None

    if not recipient:
        flash('No email address on record for this participant.', 'warning')
        return redirect(url_for('certificates.index'))

    if not (cfg and cfg.smtp_host and cfg.smtp_username and cfg.smtp_from_email):
        flash('SMTP not configured — go to Event Settings to set it up.', 'danger')
        return redirect(url_for('certificates.index'))

    try:
        png = _make_social_cert(cfg, entry, position)
        _send_social_email(cfg, recipient, entry, position, png)
        flash(f'Certificate emailed to {recipient}.', 'success')
    except Exception as exc:
        flash(f'Email failed: {exc}', 'danger')

    return redirect(url_for('certificates.index'))


def _send_social_email(cfg, recipient, entry, position, png_bytes):
    position_label = POSITION_SOCIAL.get(position, f'Position {position}')
    item_name      = entry.competition_item.name
    event_name     = cfg.event_name or 'Kalamela'
    from_name      = cfg.smtp_from_name or event_name
    from_addr      = cfg.smtp_from_email
    subject        = f'Your {position_label} certificate — {item_name} | {event_name}'

    msg            = MIMEMultipart()
    msg['From']    = f'{from_name} <{from_addr}>'
    msg['To']      = recipient
    msg['Subject'] = subject

    body = (
        f'Dear {entry.display_name},\n\n'
        f'Congratulations on achieving {position_label} in {item_name} '
        f'({entry.competition_item.category}) at {event_name}!\n\n'
        f'Please find your digital certificate attached. '
        f'Feel free to share it on Instagram or WhatsApp Stories.\n\n'
        f'Best wishes,\n{from_name}'
    )
    msg.attach(MIMEText(body, 'plain'))

    part = MIMEBase('image', 'png')
    part.set_payload(png_bytes)
    encoders.encode_base64(part)
    safe_name = f'certificate_{entry.display_name}_{item_name}.png'.replace(' ', '_')
    part.add_header('Content-Disposition', 'attachment', filename=safe_name)
    msg.attach(part)

    port = cfg.smtp_port or 587
    if cfg.smtp_use_tls:
        server = smtplib.SMTP(cfg.smtp_host, port, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        server = smtplib.SMTP_SSL(cfg.smtp_host, port, timeout=15)

    server.login(cfg.smtp_username, cfg.smtp_password or '')
    server.sendmail(from_addr, [recipient], msg.as_string())
    server.quit()


@certificates_bp.route('/awards')
def award_certificates():
    cfg         = EventConfig.query.first()
    all_results = get_all_results()
    points_map  = compute_individual_points(all_results)
    champions   = compute_individual_champions(points_map)
    kk          = compute_kalathilakam_kalaprathibha(all_results, points_map)
    bhasha      = compute_bhasha_kesari(all_results, points_map)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as zf:
        for cat, winners in champions.items():
            for w in winners:
                pdf  = _make_cert(cfg, w['name'], 'All Events', cat, f'Individual Champion — {cat}')
                safe = f'champion_{cat}_{w["name"]}.pdf'.replace(' ', '_')
                zf.writestr(safe, pdf)

        for award_name, winners in kk.items():
            for w in winners:
                pdf  = _make_cert(cfg, w['name'], 'All Events', 'All Categories', award_name)
                safe = f'{award_name}_{w["name"]}.pdf'.replace(' ', '_')
                zf.writestr(safe, pdf)

        for w in bhasha:
            pdf  = _make_cert(cfg, w['name'], 'Language Events', w['category'],
                              'Malayalam Bhasha Kesari Puraskaram')
            safe = f'BhashaKesari_{w["name"]}.pdf'.replace(' ', '_')
            zf.writestr(safe, pdf)

    zip_buf.seek(0)
    return send_file(zip_buf, mimetype='application/zip', as_attachment=True,
                     download_name='award_certificates.zip')
