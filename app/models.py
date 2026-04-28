from datetime import date, datetime
from app import db

# Association table for group members
group_members = db.Table(
    'group_members',
    db.Column('group_id', db.Integer, db.ForeignKey('group_entry.id'), primary_key=True),
    db.Column('participant_id', db.Integer, db.ForeignKey('participant.id'), primary_key=True)
)


class EventConfig(db.Model):
    __tablename__ = 'event_config'
    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(200), nullable=False, default='Leicester Kerala Community Kalamela 2026')
    event_date = db.Column(db.Date, nullable=True)
    venue = db.Column(db.String(300), nullable=True)
    cert_bg_image = db.Column(db.String(300), nullable=True)
    cert_font = db.Column(db.String(100), default='Helvetica')
    cert_font_size = db.Column(db.Integer, default=24)
    cert_font_colour = db.Column(db.String(10), default='#000000')
    cert_title_text = db.Column(db.String(200), default='Certificate of Achievement')
    cert_body_text = db.Column(db.Text, default='This is to certify that {name} has achieved {position} in {item} ({category}) at {event_name} on {date}.')
    scoresheet_blank_rows = db.Column(db.Integer, default=3)
    default_num_judges = db.Column(db.Integer, default=3)
    welcome_logo = db.Column(db.String(300), nullable=True)
    welcome_tagline = db.Column(db.String(300), nullable=True)


class Stage(db.Model):
    __tablename__ = 'stage'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    display_order = db.Column(db.Integer, default=0)
    entries = db.relationship('Entry', backref='stage', lazy=True)


class StagePlanItem(db.Model):
    """Ordered list of competition items for a stage's planning schedule."""
    __tablename__ = 'stage_plan_item'
    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey('stage.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('competition_item.id'), nullable=False)
    display_order = db.Column(db.Integer, default=0)

    stage = db.relationship('Stage')
    item = db.relationship('CompetitionItem')

    __table_args__ = (
        db.UniqueConstraint('stage_id', 'item_id', name='uq_stage_plan_item'),
    )


class CompetitionItem(db.Model):
    __tablename__ = 'competition_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    # Kids / Sub-Junior / Junior / Senior / Super Senior / Common
    category = db.Column(db.String(50), nullable=False)
    # solo / group
    item_type = db.Column(db.String(10), nullable=False, default='solo')
    max_duration_mins = db.Column(db.Integer, nullable=True)
    min_members = db.Column(db.Integer, nullable=True)
    max_members = db.Column(db.Integer, nullable=True)
    # None / Female
    gender_restriction = db.Column(db.String(10), nullable=True)
    is_custom = db.Column(db.Boolean, default=False)
    # 0 = use EventConfig.default_num_judges; 1/2/3 = item-specific override
    num_judges = db.Column(db.Integer, nullable=False, default=0)

    criteria = db.relationship('Criteria', backref='item', lazy=True,
                               order_by='Criteria.display_order', cascade='all, delete-orphan')
    entries = db.relationship('Entry', backref='competition_item', lazy=True)

    @property
    def max_marks_per_judge(self):
        return sum(c.max_marks for c in self.criteria)


class Criteria(db.Model):
    __tablename__ = 'criteria'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('competition_item.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    display_order = db.Column(db.Integer, default=0)


class Participant(db.Model):
    __tablename__ = 'participant'
    id = db.Column(db.Integer, primary_key=True)
    chest_number = db.Column(db.Integer, unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    lkc_id = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), nullable=False)  # Male / Female
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(200), nullable=True)
    parent_name = db.Column(db.String(200), nullable=True)

    individual_entries = db.relationship('Entry', backref='participant', lazy=True,
                                         foreign_keys='Entry.participant_id')
    group_memberships = db.relationship('GroupEntry', secondary=group_members,
                                        back_populates='members')

    @staticmethod
    def derive_category(dob: date) -> str:
        cutoff = date(2026, 9, 1)
        age_years = (cutoff - dob).days / 365.25
        if dob >= date(2018, 9, 1):
            return 'Kids'
        elif date(2014, 9, 1) <= dob <= date(2018, 8, 31):
            return 'Sub-Junior'
        elif date(2009, 9, 1) <= dob <= date(2014, 8, 31):
            return 'Junior'
        elif dob <= date(1991, 8, 31):
            return 'Super Senior'
        else:
            return 'Senior'

    @staticmethod
    def next_chest_number():
        last = db.session.query(db.func.max(Participant.chest_number)).scalar()
        if last is None:
            # Also check group entries
            last_group = db.session.query(db.func.max(GroupEntry.chest_number)).scalar()
            if last_group is None:
                return 101
            return last_group + 1
        last_group = db.session.query(db.func.max(GroupEntry.chest_number)).scalar() or 0
        return max(last, last_group) + 1


class GroupEntry(db.Model):
    __tablename__ = 'group_entry'
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(200), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('competition_item.id'), nullable=False)
    chest_number = db.Column(db.Integer, unique=True, nullable=False)

    item = db.relationship('CompetitionItem')
    members = db.relationship('Participant', secondary=group_members,
                              back_populates='group_memberships')
    entry = db.relationship('Entry', backref='group_entry', uselist=False,
                            foreign_keys='Entry.group_id')

    @staticmethod
    def next_chest_number():
        last_p = db.session.query(db.func.max(Participant.chest_number)).scalar() or 0
        last_g = db.session.query(db.func.max(GroupEntry.chest_number)).scalar() or 0
        return max(last_p, last_g) + 1


class Entry(db.Model):
    """One competitor (individual or group) in one event."""
    __tablename__ = 'entry'
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group_entry.id'), nullable=True)
    item_id = db.Column(db.Integer, db.ForeignKey('competition_item.id'), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey('stage.id'), nullable=True)
    running_order = db.Column(db.Integer, nullable=True)
    # waiting / performing / completed
    status = db.Column(db.String(20), default='waiting')

    is_cancelled = db.Column(db.Boolean, nullable=False, default=False)

    scores = db.relationship('Score', backref='entry', lazy=True,
                             cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='entry', lazy=True,
                                 cascade='all, delete-orphan')

    @property
    def display_name(self):
        if self.participant:
            return self.participant.full_name
        if self.group_entry:
            return self.group_entry.group_name
        return 'Unknown'

    @property
    def chest_number(self):
        if self.participant:
            return self.participant.chest_number
        if self.group_entry:
            return self.group_entry.chest_number
        return None

    @property
    def active_judges(self) -> set:
        """Judge numbers that have at least one Score record."""
        return {s.judge_number for s in self.scores}

    def judge_total(self, judge_number: int) -> float:
        return sum(
            s.marks for s in self.scores if s.judge_number == judge_number
        )

    @property
    def final_score(self) -> float:
        return sum(s.marks for s in self.scores)

    def scores_complete(self) -> bool:
        """True when every judge who has any score has scores for all criteria."""
        if not self.scores:
            return False
        num_criteria = len(self.competition_item.criteria)
        for j in self.active_judges:
            if sum(1 for s in self.scores if s.judge_number == j) < num_criteria:
                return False
        return True


class Score(db.Model):
    __tablename__ = 'score'
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('entry.id'), nullable=False)
    judge_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3
    criteria_id = db.Column(db.Integer, db.ForeignKey('criteria.id'), nullable=False)
    marks = db.Column(db.Float, nullable=False, default=0)

    criteria = db.relationship('Criteria')

    __table_args__ = (
        db.UniqueConstraint('entry_id', 'judge_number', 'criteria_id'),
    )


class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    entry_id = db.Column(db.Integer, db.ForeignKey('entry.id'), nullable=False)
    judge_number = db.Column(db.Integer, nullable=False)
    criteria_id = db.Column(db.Integer, db.ForeignKey('criteria.id'), nullable=False)
    old_value = db.Column(db.Float, nullable=True)
    new_value = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(500), nullable=True)

    criteria_rel = db.relationship('Criteria')
