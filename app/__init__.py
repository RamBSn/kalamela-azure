import os
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

db = SQLAlchemy()

# Default admin password — override via ADMIN_PASSWORD env var in production
_DEFAULT_ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password')


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    # Azure: set DATA_DIR=/home/kalamela for persistent SQLite storage.
    # Locally: falls back to instance/ and static/uploads/ as before.
    data_dir = os.environ.get('DATA_DIR', '').strip()
    if data_dir:
        db_path = os.path.join(data_dir, 'kalamela.db')
        upload_folder = os.path.join(data_dir, 'uploads')
        backup_folder = os.path.join(data_dir, 'backups')
        hash_file = os.path.join(data_dir, 'admin.hash')
    else:
        db_path = os.path.join(app.instance_path, 'kalamela.db')
        upload_folder = os.path.join(app.root_path, 'static', 'uploads')
        backup_folder = os.path.join(os.path.dirname(app.root_path), 'backups')
        hash_file = os.path.join(app.instance_path, 'admin.hash')

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'kalamela-local-secret-2026')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    app.config['DATABASE_PATH'] = db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.config['BACKUP_FOLDER'] = backup_folder
    # Extra password for Reset / Restore operations.
    # Set via DATA_RESET_PASSWORD env var (sourced from Key Vault on Azure).
    # If not set, the check is skipped — intended for local development only.
    app.config['DATA_RESET_PASSWORD'] = os.environ.get('DATA_RESET_PASSWORD', '')
    # Default hash; tests always use this (no file loading in test mode)
    app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash(_DEFAULT_ADMIN_PASSWORD)

    if test_config:
        app.config.update(test_config)
        if 'ADMIN_PASSWORD' in test_config:
            app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash(test_config['ADMIN_PASSWORD'])
    else:
        # Production only: load persisted hash from disk if a password change was saved
        if os.path.exists(hash_file):
            with open(hash_file) as _f:
                app.config['ADMIN_PASSWORD_HASH'] = _f.read().strip()
        app.config['ADMIN_HASH_FILE'] = hash_file

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(backup_folder, exist_ok=True)

    db.init_app(app)

    from app.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.setup import setup_bp
    from app.routes.participants import participants_bp
    from app.routes.schedule import schedule_bp
    from app.routes.scores import scores_bp
    from app.routes.results import results_bp
    from app.routes.certificates import certificates_bp
    from app.routes.scoresheets import scoresheets_bp
    from app.routes.data import data_bp
    from app.routes.planning import planning_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(setup_bp, url_prefix='/setup')
    app.register_blueprint(participants_bp, url_prefix='/participants')
    app.register_blueprint(schedule_bp, url_prefix='/schedule')
    app.register_blueprint(planning_bp, url_prefix='/planning')
    app.register_blueprint(scores_bp, url_prefix='/scores')
    app.register_blueprint(results_bp, url_prefix='/results')
    app.register_blueprint(certificates_bp, url_prefix='/certificates')
    app.register_blueprint(scoresheets_bp, url_prefix='/scoresheets')
    app.register_blueprint(data_bp, url_prefix='/data')

    @app.context_processor
    def inject_auth():
        return {'is_admin': session.get('admin_logged_in', False)}

    with app.app_context():
        db.create_all()
        _apply_migrations()
        from app.seed_data import seed_if_empty
        seed_if_empty()

    return app


def _apply_migrations():
    """Lightweight schema migrations for columns added after initial release."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    if 'competition_item' in tables:
        existing = {c['name'] for c in inspector.get_columns('competition_item')}
        if 'num_judges' not in existing:
            db.session.execute(
                text('ALTER TABLE competition_item ADD COLUMN num_judges INTEGER NOT NULL DEFAULT 0')
            )
            db.session.commit()

    if 'event_config' in tables:
        existing = {c['name'] for c in inspector.get_columns('event_config')}
        if 'default_num_judges' not in existing:
            db.session.execute(
                text('ALTER TABLE event_config ADD COLUMN default_num_judges INTEGER NOT NULL DEFAULT 3')
            )
            db.session.commit()

    if 'entry' in tables:
        existing = {c['name'] for c in inspector.get_columns('entry')}
        if 'is_cancelled' not in existing:
            db.session.execute(
                text('ALTER TABLE entry ADD COLUMN is_cancelled INTEGER NOT NULL DEFAULT 0')
            )
            db.session.commit()

    if 'event_config' in tables:
        existing = {c['name'] for c in inspector.get_columns('event_config')}
        for col, ddl in [
            ('welcome_logo',       'ALTER TABLE event_config ADD COLUMN welcome_logo VARCHAR(300)'),
            ('welcome_tagline',    'ALTER TABLE event_config ADD COLUMN welcome_tagline VARCHAR(300)'),
            ('cert_heading_colour','ALTER TABLE event_config ADD COLUMN cert_heading_colour VARCHAR(10) DEFAULT "#8b6914"'),
            ('cert_title_colour',  'ALTER TABLE event_config ADD COLUMN cert_title_colour VARCHAR(10) DEFAULT "#1a1a2e"'),
            ('cert_name_colour',   'ALTER TABLE event_config ADD COLUMN cert_name_colour VARCHAR(10) DEFAULT "#8b6914"'),
        ]:
            if col not in existing:
                db.session.execute(text(ddl))
                db.session.commit()
