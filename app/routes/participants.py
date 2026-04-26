import re
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.datastructures import ImmutableMultiDict
from app import db
from app.models import Participant, GroupEntry, Entry, CompetitionItem
from app.auth import login_required

participants_bp = Blueprint('participants', __name__)

CATEGORIES = ['Kids', 'Sub-Junior', 'Junior', 'Senior', 'Super Senior', 'Common']
FEMALE_ONLY_ITEMS = ['Thiruvathira', 'Oppana', 'Margamkali']


def check_eligibility(participant, item):
    """Return list of warning strings. Empty list = OK."""
    warnings = []

    # Gender restriction
    if item.gender_restriction == 'Female' and participant.gender != 'Female':
        warnings.append(f'"{item.name}" is for females only.')

    # Category check — participant cannot compete in higher category if own category has the event
    if item.category != 'Common':
        own_cat_has_item = CompetitionItem.query.filter_by(
            name=item.name, category=participant.category
        ).first()
        if own_cat_has_item and item.category != participant.category:
            warnings.append(
                f'Participant\'s category is "{participant.category}". '
                f'This item is available in their own category — cannot compete in "{item.category}".'
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


@participants_bp.route('/register', methods=['GET', 'POST'])
def register_individual():
    items = CompetitionItem.query.order_by(
        CompetitionItem.category, CompetitionItem.name
    ).all()

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

        category = Participant.derive_category(dob)

        participant = Participant(
            chest_number=Participant.next_chest_number(),
            full_name=request.form['full_name'].strip(),
            date_of_birth=dob,
            category=category,
            lkc_id=lkc_id,
            gender=request.form['gender'],
            phone=phone,
            email=request.form.get('email', '').strip() or None,
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
                warnings.append(
                    f'{m.full_name}: category mismatch '
                    f'({m.category} participant in a {item.category} event).'
                )
            if not Entry.query.filter_by(participant_id=m.id, item_id=item_id).first():
                warnings.append(
                    f'{m.full_name} is not individually registered for "{item.name}".'
                )

        override = request.form.get('override_warnings') == '1'
        if warnings and not override:
            flash('Group eligibility warnings — confirm override to proceed.', 'warning')
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

    p = Participant.query.filter_by(lkc_id=lkc_id).first()
    if not p:
        return jsonify({'found': False})

    result = {
        'found': True,
        'id': p.id,
        'full_name': p.full_name,
        'category': p.category,
        'gender': p.gender,
        'chest_number': p.chest_number,
        'eligible': True,
        'eligibility_issues': [],
    }

    if item_id:
        item = CompetitionItem.query.get(item_id)
        if item:
            issues = []
            # 1. Age category must match (Common events accept everyone)
            if item.category != 'Common' and p.category != item.category:
                issues.append(
                    f'Category mismatch: participant is {p.category}, '
                    f'this event is for {item.category}.'
                )
            # 2. Participant must be individually registered for this group event
            registered = Entry.query.filter_by(
                participant_id=p.id, item_id=item_id
            ).first()
            if not registered:
                issues.append(
                    f'Not individually registered for "{item.name}". '
                    f'Register the participant for this event first.'
                )
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


@participants_bp.route('/api/category-from-dob')
def category_from_dob():
    dob_str = request.args.get('dob', '')
    try:
        dob = date.fromisoformat(dob_str)
        return jsonify({'category': Participant.derive_category(dob)})
    except Exception:
        return jsonify({'category': ''})
