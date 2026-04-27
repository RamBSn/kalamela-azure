import re
import logging
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from markupsafe import Markup, escape
from werkzeug.datastructures import ImmutableMultiDict
from app import db
from app.models import Participant, GroupEntry, Entry, CompetitionItem
from app.auth import login_required

logger = logging.getLogger(__name__)

participants_bp = Blueprint('participants', __name__)

CATEGORIES = ['Kids', 'Sub-Junior', 'Junior', 'Senior', 'Super Senior', 'Common']
FEMALE_ONLY_ITEMS = ['Thiruvathira', 'Oppana', 'Margamkali']

LKC_MEMBERSHIP_API = 'https://leicesterkeralacommunity.org.uk/mobileapp/api/auth/login'
LKC_JOIN_URL = 'https://www.leicesterkeralacommunity.org.uk/online'


def _verify_lkc_membership(lkc_id: str, email: str):
    """
    Check LKC membership status via the community API.
    Returns ('active'|'inactive'|'error', message, holder_name).
    'error' means the API was unreachable — caller should warn and proceed.
    Success is determined by membership_status == 'active' in the response body.
    """
    import json as _j
    import urllib.request as _ur
    import urllib.error as _ue

    logger.info('LKC membership check — lkc_id=%s, email=%s', lkc_id, email)

    payload = _j.dumps({'lkc_id': lkc_id, 'email': email}).encode('utf-8')
    req = _ur.Request(
        LKC_MEMBERSHIP_API,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0',
        },
        method='POST',
    )
    try:
        with _ur.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode('utf-8')
            body = _j.loads(raw)
        logger.debug('LKC membership check — response: %s', raw)

        user              = body.get('data', {}).get('user', {})
        membership_status = user.get('membership_status', '')

        if membership_status == 'active':
            first  = (user.get('first_name') or '').strip()
            last   = (user.get('last_name')  or '').strip()
            holder = f'{first} {last}'.strip()
            logger.info('LKC membership check — ACTIVE for %s (%s %s)', lkc_id, first, last)
            return 'active', 'LKC membership is active.', holder

        logger.warning(
            'LKC membership check — NOT active for %s: membership_status=%r',
            lkc_id, membership_status
        )
        return 'inactive', 'Membership is not active.', ''

    except _ue.HTTPError as e:
        raw_err = ''
        try:
            raw_err = e.read().decode('utf-8')
            err_body = _j.loads(raw_err)
            msg = err_body.get('messages', {}).get('error') or f'HTTP {e.code} from membership API.'
        except Exception:
            msg = f'HTTP {e.code} from membership API.'
        logger.warning(
            'LKC membership check — HTTP %s for %s email=%s: %s | raw: %s',
            e.code, lkc_id, email, msg, raw_err
        )
        return 'inactive', msg, ''

    except Exception as exc:
        logger.error(
            'LKC membership check — unreachable for %s email=%s: %s',
            lkc_id, email, exc, exc_info=True
        )
        return 'error', f'Could not reach LKC server ({exc}).', ''


def check_eligibility(participant, item):
    """Return list of warning strings. Empty list = OK."""
    warnings = []

    # Gender restriction
    if item.gender_restriction == 'Female' and participant.gender != 'Female':
        warnings.append(f'"{item.name}" is for females only.')

    # Category eligibility
    if item.category != 'Common' and item.category != participant.category:
        if participant.category == 'Super Senior' and item.category == 'Senior':
            # Super Seniors may enter Senior events UNLESS the same event exists in Super Senior
            if CompetitionItem.query.filter_by(name=item.name, category='Super Senior').first():
                warnings.append(
                    f'"{item.name}" is available in the Super Senior category. '
                    'Super Seniors must compete in their own category for this event.'
                )
        else:
            warnings.append(
                f'This event is for the {item.category} category. '
                f'Participant\'s category is "{participant.category}".'
            )

    # Max events check
    current_entries = Entry.query.filter_by(participant_id=participant.id).all()
    solo_count = sum(1 for e in current_entries if e.competition_item.item_type == 'solo')
    group_count = sum(1 for e in current_entries if e.competition_item.item_type == 'group')
    new_type = item.item_type

    if new_type == 'solo':
        if group_count >= 2 and solo_count >= 2:
            warnings.append('Max events reached (2 solo + 2 group). Cannot add more solo events.')
        elif group_count < 1 and solo_count >= 3:
            warnings.append('Max 3 solo events allowed (with at most 1 group).')
        elif solo_count + group_count >= 4:
            warnings.append('Max 4 events per participant reached.')
    else:
        if solo_count >= 3 and group_count >= 1:
            warnings.append('Max events reached (3 solo + 1 group). Cannot add more group events.')
        elif solo_count < 3 and group_count >= 2:
            warnings.append('Max 2 group events allowed.')
        elif solo_count + group_count >= 4:
            warnings.append('Max 4 events per participant reached.')

    return warnings


@participants_bp.route('/')
@login_required
def list_participants():
    search = request.args.get('q', '').strip()
    query = Participant.query
    if search:
        query = query.filter(
            (Participant.full_name.ilike(f'%{search}%')) |
            (Participant.lkc_id.ilike(f'%{search}%'))
        )
    participants = query.order_by(Participant.chest_number).all()
    return render_template('participants/list.html', participants=participants, search=search)


def _ss_excluded_senior_ids():
    """Return the IDs of Senior-category items that Super Seniors may NOT enter
    (because the same event exists in the Super Senior category)."""
    result = []
    for ss_item in CompetitionItem.query.filter_by(category='Super Senior').all():
        senior_equiv = CompetitionItem.query.filter_by(
            name=ss_item.name, category='Senior'
        ).first()
        if senior_equiv:
            result.append(senior_equiv.id)
    return result


@participants_bp.route('/register', methods=['GET', 'POST'])
def register_individual():
    items = CompetitionItem.query.order_by(
        CompetitionItem.category, CompetitionItem.name
    ).all()
    ss_excluded = _ss_excluded_senior_ids()

    today = date.today().isoformat()

    if request.method == 'POST':
        def _re_render(warnings=None, error=None):
            if error:
                flash(error, 'danger')
            return render_template(
                'participants/register_individual.html',
                items=items,
                warnings=warnings or [],
                form_data=request.form,
                categories=CATEGORIES,
                today=today,
                ss_excluded_senior_ids=ss_excluded,
            )

        # --- Hard-block: event count (no override offered) ---
        selected_item_ids = request.form.getlist('items[]')
        n_solo = n_group = 0
        for iid in selected_item_ids:
            obj = CompetitionItem.query.get(int(iid))
            if obj:
                if obj.item_type == 'solo':
                    n_solo += 1
                else:
                    n_group += 1
        count_valid = (
            (n_solo <= 3 and n_group <= 1 and n_solo + n_group <= 4) or
            (n_solo <= 2 and n_group <= 2 and n_solo + n_group <= 4)
        )
        if not count_valid:
            return _re_render(
                error=(
                    f'Too many events selected ({n_solo} solo, {n_group} group). '
                    'Maximum allowed: 3 solo + 1 group, or 2 solo + 2 group.'
                )
            )

        # --- Validate DOB ---
        dob_str = request.form['date_of_birth'].strip()
        try:
            dob = date.fromisoformat(dob_str)
        except ValueError:
            return _re_render(error='Invalid date of birth.')
        if dob.year < 1900:
            return _re_render(error='Date of birth year must be 1900 or later.')
        if dob > date.today():
            return _re_render(error='Date of birth cannot be in the future.')

        # --- Validate phone ---
        phone = request.form['phone'].strip()
        if not (phone.startswith('07') and len(phone) == 11 and phone.isdigit()):
            return _re_render(error='Phone number must be in 07XXXXXXXXX format (11 digits, starting with 07).')

        # --- Validate LKC ID ---
        lkc_id = request.form['lkc_id'].strip().upper()
        if not re.fullmatch(r'LKC\d{3,4}', lkc_id):
            return _re_render(error='LKC ID must be in LKC### or LKC#### format (LKC followed by 3 or 4 digits).')

        # --- Validate email (required for membership check) ---
        email_val = request.form.get('email', '').strip()
        if not email_val:
            return _re_render(error='Email address is required for LKC membership verification.')

        # --- Verify LKC membership ---
        mem_status, mem_msg, _ = _verify_lkc_membership(lkc_id, email_val)
        if mem_status == 'inactive':
            flash(Markup(
                f'{escape(mem_msg)} &mdash; '
                f'<a href="{LKC_JOIN_URL}" target="_blank" rel="noopener noreferrer">'
                f'Register or renew your LKC membership</a>'
            ), 'danger')
            return _re_render()
        if mem_status == 'error':
            flash(f'LKC membership check unavailable ({mem_msg}). Proceeding with registration.', 'warning')

        category = Participant.derive_category(dob)

        participant = Participant(
            chest_number=Participant.next_chest_number(),
            full_name=request.form['full_name'].strip(),
            date_of_birth=dob,
            category=category,
            lkc_id=lkc_id,
            gender=request.form['gender'],
            phone=phone,
            email=email_val or None,
            parent_name=request.form.get('parent_name', '').strip() or None,
        )
        db.session.add(participant)
        db.session.flush()

        # Enrol in selected events — hard-block on any eligibility issue
        all_warnings = []

        for item_id in selected_item_ids:
            item = CompetitionItem.query.get(int(item_id))
            if not item:
                continue
            w = check_eligibility(participant, item)
            all_warnings.extend(w)

        if all_warnings:
            db.session.rollback()
            return _re_render(warnings=all_warnings)

        for item_id in selected_item_ids:
            item = CompetitionItem.query.get(int(item_id))
            if item:
                db.session.add(Entry(participant_id=participant.id, item_id=item.id))

        db.session.commit()
        flash(f'Registered {participant.full_name} (Chest #{participant.chest_number}).', 'success')
        return redirect(url_for('participants.register_individual'))

    return render_template(
        'participants/register_individual.html',
        items=items,
        warnings=[],
        form_data=ImmutableMultiDict(),
        categories=CATEGORIES,
        today=today,
        ss_excluded_senior_ids=ss_excluded,
    )


@participants_bp.route('/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
def edit_participant(pid):
    participant = Participant.query.get_or_404(pid)
    items = CompetitionItem.query.order_by(
        CompetitionItem.category, CompetitionItem.name
    ).all()

    if request.method == 'POST':
        dob_str = request.form['date_of_birth']
        dob = date.fromisoformat(dob_str)
        participant.full_name = request.form['full_name'].strip()
        participant.date_of_birth = dob
        participant.category = Participant.derive_category(dob)
        participant.lkc_id = request.form['lkc_id'].strip()
        participant.gender = request.form['gender']
        participant.phone = request.form['phone'].strip()
        participant.email = request.form.get('email', '').strip() or None
        participant.parent_name = request.form.get('parent_name', '').strip() or None

        # Update event enrolments — remove old solo entries (keep group entries)
        for e in list(participant.individual_entries):
            db.session.delete(e)
        db.session.flush()

        selected_items = request.form.getlist('items[]')
        for item_id in selected_items:
            item = CompetitionItem.query.get(int(item_id))
            if item:
                db.session.add(Entry(participant_id=participant.id, item_id=item.id))

        db.session.commit()
        flash(f'{participant.full_name} updated.', 'success')
        return redirect(url_for('participants.list_participants'))

    enrolled_ids = [e.item_id for e in participant.individual_entries]
    return render_template(
        'participants/edit.html',
        participant=participant,
        items=items,
        enrolled_ids=enrolled_ids,
        categories=CATEGORIES,
    )


@participants_bp.route('/<int:pid>/delete', methods=['POST'])
@login_required
def delete_participant(pid):
    participant = Participant.query.get_or_404(pid)
    name = participant.full_name
    db.session.delete(participant)
    db.session.commit()
    flash(f'{name} removed.', 'success')
    return redirect(url_for('participants.list_participants'))


# ── Groups ────────────────────────────────────────────────────────────────────

@participants_bp.route('/groups/register', methods=['GET', 'POST'])
def register_group():
    items = CompetitionItem.query.filter_by(item_type='group').order_by(
        CompetitionItem.category, CompetitionItem.name
    ).all()

    if request.method == 'POST':
        item_id = int(request.form['item_id'])
        item = CompetitionItem.query.get_or_404(item_id)
        member_ids = request.form.getlist('members[]')
        member_ids = [int(m) for m in member_ids if m]

        members = Participant.query.filter(Participant.id.in_(member_ids)).all()
        n = len(members)

        warnings = []
        if item.min_members and n < item.min_members:
            warnings.append(f'Minimum {item.min_members} members required for {item.name}.')
        if item.max_members and n > item.max_members:
            warnings.append(f'Maximum {item.max_members} members allowed for {item.name}.')
        if item.gender_restriction == 'Female':
            non_female = [m.full_name for m in members if m.gender != 'Female']
            if non_female:
                warnings.append(f'{item.name} is females only. Non-female members: {", ".join(non_female)}.')

        # Per-member: category match and individual registration
        for m in members:
            if item.category != 'Common' and m.category != item.category:
                if m.category == 'Super Senior' and item.category == 'Senior':
                    # Super Senior exception: allowed unless same event exists in Super Senior
                    if CompetitionItem.query.filter_by(name=item.name, category='Super Senior').first():
                        warnings.append(
                            f'{m.full_name}: "{item.name}" is available in the Super Senior '
                            'category — must compete in their own category for this event.'
                        )
                else:
                    warnings.append(
                        f'{m.full_name}: category mismatch '
                        f'({m.category} participant in a {item.category} event).'
                    )
            if not Entry.query.filter_by(participant_id=m.id, item_id=item_id).first():
                warnings.append(
                    f'{m.full_name} is not individually registered for "{item.name}".'
                )

        if warnings:
            flash('Registration blocked — eligibility errors must be resolved.', 'danger')
            selected = [{'id': m.id, 'full_name': m.full_name,
                         'category': m.category, 'gender': m.gender,
                         'chest_number': m.chest_number} for m in members]
            return render_template(
                'participants/register_group.html',
                items=items,
                selected_members=selected,
                warnings=warnings,
                form_data=request.form,
            )

        group = GroupEntry(
            group_name=request.form['group_name'].strip(),
            item_id=item_id,
            chest_number=GroupEntry.next_chest_number(),
        )
        group.members = members
        db.session.add(group)
        db.session.flush()
        db.session.add(Entry(group_id=group.id, item_id=item_id))
        db.session.commit()
        flash(f'Group "{group.group_name}" registered (Chest #{group.chest_number}).', 'success')
        return redirect(url_for('participants.list_groups'))

    return render_template(
        'participants/register_group.html',
        items=items,
        selected_members=[],
        warnings=[],
        form_data=ImmutableMultiDict(),
    )


@participants_bp.route('/api/by-lkc-id')
def participant_by_lkc_id():
    lkc_id = request.args.get('id', '').strip()
    item_id = request.args.get('item_id', type=int)

    participants = Participant.query.filter_by(lkc_id=lkc_id).all()
    if not participants:
        return jsonify({'found': False})

    item = CompetitionItem.query.get(item_id) if item_id else None

    def build_result(p):
        result = {
            'found': True,
            'id': p.id,
            'lkc_id': p.lkc_id,
            'full_name': p.full_name,
            'category': p.category,
            'gender': p.gender,
            'chest_number': p.chest_number,
            'eligible': True,
            'eligibility_issues': [],
        }
        if item:
            issues = []
            if item.category != 'Common' and p.category != item.category:
                if p.category == 'Super Senior' and item.category == 'Senior':
                    if CompetitionItem.query.filter_by(name=item.name, category='Super Senior').first():
                        issues.append(
                            f'"{item.name}" is available in the Super Senior category. '
                            'Super Seniors must compete in their own category for this event.'
                        )
                else:
                    issues.append(
                        f'Category mismatch: participant is {p.category}, '
                        f'this event is for {item.category}.'
                    )
            if not Entry.query.filter_by(participant_id=p.id, item_id=item_id).first():
                issues.append(
                    f'Not individually registered for "{item.name}". '
                    f'Register the participant for this event first.'
                )
            if issues:
                result['eligible'] = False
                result['eligibility_issues'] = issues
                result['eligible_group_items'] = _eligible_group_items_for(p)
        return result

    candidates = [build_result(p) for p in participants]

    if len(candidates) == 1:
        return jsonify(candidates[0])

    return jsonify({'found': True, 'multiple': True, 'candidates': candidates})


def _eligible_group_items_for(participant):
    """Return group events the participant is individually registered for
    and is category-eligible to enter (used in add-member error messages)."""
    eligible = []
    for entry in Entry.query.filter_by(participant_id=participant.id).all():
        gi = CompetitionItem.query.get(entry.item_id)
        if not gi or gi.item_type != 'group':
            continue
        # Category check (same logic as add-member validation)
        if gi.category != 'Common' and participant.category != gi.category:
            if participant.category == 'Super Senior' and gi.category == 'Senior':
                if CompetitionItem.query.filter_by(name=gi.name, category='Super Senior').first():
                    continue  # blocked — exists in SS category
            else:
                continue  # wrong category
        eligible.append({'id': gi.id, 'name': gi.name, 'category': gi.category})
    return eligible


@participants_bp.route('/api/participant-by-id')
def participant_by_db_id():
    """Re-validate an already-added group member against a (possibly changed) event."""
    pid = request.args.get('id', type=int)
    item_id = request.args.get('item_id', type=int)
    if not pid:
        return jsonify({'found': False})
    p = Participant.query.get(pid)
    if not p:
        return jsonify({'found': False})

    result = {
        'found': True, 'id': p.id, 'eligible': True, 'eligibility_issues': [],
    }
    if item_id:
        item = CompetitionItem.query.get(item_id)
        if item:
            issues = []
            if item.category != 'Common' and p.category != item.category:
                if p.category == 'Super Senior' and item.category == 'Senior':
                    if CompetitionItem.query.filter_by(name=item.name, category='Super Senior').first():
                        issues.append(
                            f'"{item.name}" is in the Super Senior category — '
                            'must compete in their own category.'
                        )
                else:
                    issues.append(
                        f'Category mismatch: {p.category} participant in a {item.category} event.'
                    )
            if not Entry.query.filter_by(participant_id=p.id, item_id=item_id).first():
                issues.append(f'Not individually registered for "{item.name}".')
            if issues:
                result['eligible'] = False
                result['eligibility_issues'] = issues
    return jsonify(result)


@participants_bp.route('/groups')
def list_groups():
    groups = GroupEntry.query.order_by(GroupEntry.chest_number).all()
    return render_template('participants/groups.html', groups=groups)


@participants_bp.route('/groups/<int:gid>/delete', methods=['POST'])
@login_required
def delete_group(gid):
    group = GroupEntry.query.get_or_404(gid)
    name = group.group_name
    db.session.delete(group)
    db.session.commit()
    flash(f'Group "{name}" removed.', 'success')
    return redirect(url_for('participants.list_groups'))


@participants_bp.route('/groups/<int:gid>/edit', methods=['GET', 'POST'])
@login_required
def edit_group(gid):
    group = GroupEntry.query.get_or_404(gid)
    item = group.item

    if request.method == 'POST':
        group_name = request.form.get('group_name', '').strip() or group.group_name
        member_ids = [int(m) for m in request.form.getlist('members[]') if m]
        members = Participant.query.filter(Participant.id.in_(member_ids)).all()
        n = len(members)

        warnings = []
        if item.min_members and n < item.min_members:
            warnings.append(f'Minimum {item.min_members} members required for {item.name}.')
        if item.max_members and n > item.max_members:
            warnings.append(f'Maximum {item.max_members} members allowed for {item.name}.')
        if item.gender_restriction == 'Female':
            non_female = [m.full_name for m in members if m.gender != 'Female']
            if non_female:
                warnings.append(
                    f'{item.name} is females only. Non-female members: {", ".join(non_female)}.'
                )
        for m in members:
            if item.category != 'Common' and m.category != item.category:
                if m.category == 'Super Senior' and item.category == 'Senior':
                    if CompetitionItem.query.filter_by(name=item.name, category='Super Senior').first():
                        warnings.append(
                            f'{m.full_name}: "{item.name}" is available in the Super Senior '
                            'category — must compete in their own category for this event.'
                        )
                else:
                    warnings.append(
                        f'{m.full_name}: category mismatch '
                        f'({m.category} participant in a {item.category} event).'
                    )
            if not Entry.query.filter_by(participant_id=m.id, item_id=item.id).first():
                warnings.append(
                    f'{m.full_name} is not individually registered for "{item.name}".'
                )

        if warnings:
            flash('Update blocked — eligibility errors must be resolved.', 'danger')
            selected = [{'id': m.id, 'full_name': m.full_name,
                         'category': m.category, 'gender': m.gender,
                         'chest_number': m.chest_number} for m in members]
            return render_template(
                'participants/edit_group.html',
                group=group, item=item,
                selected_members=selected,
                warnings=warnings,
                form_data=request.form,
            )

        group.group_name = group_name
        group.members = members
        db.session.commit()
        flash(f'Group "{group.group_name}" updated.', 'success')
        return redirect(url_for('participants.list_groups'))

    selected = [{'id': m.id, 'full_name': m.full_name,
                 'category': m.category, 'gender': m.gender,
                 'chest_number': m.chest_number} for m in group.members]
    return render_template(
        'participants/edit_group.html',
        group=group, item=item,
        selected_members=selected,
        warnings=[],
        form_data=ImmutableMultiDict(),
    )


@participants_bp.route('/api/category-from-dob')
def category_from_dob():
    dob_str = request.args.get('dob', '')
    try:
        dob = date.fromisoformat(dob_str)
        return jsonify({'category': Participant.derive_category(dob)})
    except Exception:
        return jsonify({'category': ''})


@participants_bp.route('/api/verify-membership', methods=['POST'])
def verify_membership_api():
    """Proxy the LKC membership check — used by the registration form via AJAX."""
    data = request.get_json(silent=True) or {}
    lkc_id = data.get('lkc_id', '').strip().upper()
    email = data.get('email', '').strip()
    if not lkc_id or not email:
        return jsonify({'status': 'error', 'message': 'LKC ID and email are required.'})
    status, message, holder_name = _verify_lkc_membership(lkc_id, email)
    return jsonify({'status': status, 'message': message,
                    'join_url': LKC_JOIN_URL, 'holder_name': holder_name})
