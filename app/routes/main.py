from flask import Blueprint, render_template, session, redirect, url_for
from app import db
from app.models import EventConfig, Participant, Entry, Stage, CompetitionItem

main_bp = Blueprint('main', __name__)


@main_bp.context_processor
def inject_event():
    cfg = EventConfig.query.first()
    if cfg:
        return {
            'event_name': cfg.event_name,
            'event_date': cfg.event_date.strftime('%d %B %Y') if cfg.event_date else '',
        }
    return {'event_name': 'Leicester Kerala Community Kalamela 2026', 'event_date': ''}


@main_bp.route('/')
def welcome():
    cfg = EventConfig.query.first()
    return render_template('welcome.html', cfg=cfg)


@main_bp.route('/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next='/dashboard'))

    total_participants = Participant.query.count()
    total_entries = Entry.query.count()
    scored = sum(1 for e in Entry.query.all() if e.scores_complete())
    pending = total_entries - scored

    stats = {
        'participants': total_participants,
        'entries': total_entries,
        'scored': scored,
        'pending': pending,
        'stages': Stage.query.count(),
        'item_count': CompetitionItem.query.count(),
    }
    return render_template('dashboard.html', stats=stats)
