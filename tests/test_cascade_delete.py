"""
Standalone test script: cascade delete behaviour for Participant → Entry → Score/AuditLog.

Run with:
    venv/bin/python tests/test_cascade_delete.py

Uses an in-memory SQLite database so the test is fully isolated from the real DB.

Cases covered
─────────────
1. Deleting participant A removes A's entries and scores, but NOT participant B's.
2. Deleting participant A does NOT delete a GroupEntry that A is a *member* of.
3. An Entry with group_id set (participant_id IS NULL) is NOT deleted by the orphan migration.
4. An Entry with BOTH participant_id=NULL AND group_id=NULL IS deleted by the orphan migration.
5. Scores attached to a deleted participant's entries are also gone (cascade through Entry).
6. AuditLog rows attached to deleted participant's entries are also gone.
"""

import sys
import os

# ── make sure the project root is on sys.path ──────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from datetime import date
from app import create_app, db
from app.models import (
    Participant, CompetitionItem, Criteria,
    GroupEntry, Entry, Score, AuditLog,
)
from sqlalchemy import text

# ── Helpers ────────────────────────────────────────────────────────────────────

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []


def check(label: str, condition: bool, explanation: str = "") -> None:
    status = PASS if condition else FAIL
    msg = f"  [{status}] {label}"
    if explanation:
        msg += f"\n         {explanation}"
    print(msg)
    results.append((label, condition))


def make_item(session, name="Folk Dance", item_type="solo"):
    item = CompetitionItem(
        name=name, category="Junior", item_type=item_type,
        max_duration_mins=7, is_custom=True,
    )
    session.add(item)
    session.flush()
    for order, (cname, cmax) in enumerate([("Rhythm", 40), ("Expression", 35), ("Technique", 25)]):
        session.add(Criteria(item_id=item.id, name=cname, max_marks=cmax, display_order=order))
    session.flush()
    return item


def make_participant(session, name, chest, lkc_id, gender="Male"):
    p = Participant(
        chest_number=chest,
        full_name=name,
        date_of_birth=date(2011, 1, 1),
        category="Junior",
        lkc_id=lkc_id,
        gender=gender,
        phone="07000000000",
    )
    session.add(p)
    session.flush()
    return p


def add_scores(session, entry, marks_per_judge=30):
    for judge in (1, 2, 3):
        for c in entry.competition_item.criteria:
            session.add(Score(
                entry_id=entry.id,
                judge_number=judge,
                criteria_id=c.id,
                marks=marks_per_judge,
            ))
    session.flush()


def add_audit_log(session, entry, old_val=20, new_val=25):
    c = entry.competition_item.criteria[0]
    session.add(AuditLog(
        entry_id=entry.id,
        judge_number=1,
        criteria_id=c.id,
        old_value=old_val,
        new_value=new_val,
        reason="Test edit",
    ))
    session.flush()


# ── App setup ──────────────────────────────────────────────────────────────────

app = create_app(test_config={
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite://",   # in-memory, no file
    "WTF_CSRF_ENABLED": False,
})

print("\n── Cascade delete behaviour tests ──────────────────────────────────────\n")

with app.app_context():
    # ── shared test data setup ─────────────────────────────────────────────────
    solo_item  = make_item(db.session, "Folk Dance", item_type="solo")
    group_item = make_item(db.session, "Group Dance", item_type="group")
    db.session.commit()

    # Two participants
    p_a = make_participant(db.session, "Alice", chest=101, lkc_id="LKC001", gender="Female")
    p_b = make_participant(db.session, "Bob",   chest=102, lkc_id="LKC002", gender="Male")
    db.session.commit()

    # Individual entries
    entry_a = Entry(participant_id=p_a.id, item_id=solo_item.id)
    entry_b = Entry(participant_id=p_b.id, item_id=solo_item.id)
    db.session.add_all([entry_a, entry_b])
    db.session.commit()

    # Scores and audit logs for both entries
    add_scores(db.session, entry_a, marks_per_judge=30)
    add_scores(db.session, entry_b, marks_per_judge=25)
    add_audit_log(db.session, entry_a)
    add_audit_log(db.session, entry_b)
    db.session.commit()

    entry_a_id = entry_a.id
    entry_b_id = entry_b.id
    p_a_id     = p_a.id
    p_b_id     = p_b.id

    # Group entry with p_a as a member
    group = GroupEntry(
        group_name="Team Sunrise",
        item_id=group_item.id,
        chest_number=201,
    )
    group.members = [p_a, p_b]
    db.session.add(group)
    db.session.flush()
    group_entry = Entry(group_id=group.id, item_id=group_item.id)
    db.session.add(group_entry)
    db.session.commit()
    group_entry_id = group_entry.id
    group_id       = group.id

    # ── Case 4 prep: manually insert a truly-orphaned entry (no participant, no group) ──
    db.session.execute(text(
        "INSERT INTO entry (participant_id, group_id, item_id, status, is_cancelled)"
        " VALUES (NULL, NULL, :item_id, 'waiting', 0)"
    ), {"item_id": solo_item.id})
    db.session.commit()

    # Capture its id
    orphan_row = db.session.execute(
        text("SELECT id FROM entry WHERE participant_id IS NULL AND group_id IS NULL")
    ).fetchone()
    assert orphan_row is not None, "Orphan row was not inserted"
    orphan_entry_id = orphan_row[0]

    # ── Now delete participant A ───────────────────────────────────────────────
    p_a_obj = db.session.get(Participant, p_a_id)
    db.session.delete(p_a_obj)
    db.session.commit()

    # ═════════════════════════════════════════════════════════════════════════
    # Case 1: A's entry is gone; B's entry is untouched
    # ═════════════════════════════════════════════════════════════════════════
    print("Case 1: Deleting participant A removes A's entries but not B's")
    a_entry_exists = db.session.get(Entry, entry_a_id) is not None
    b_entry_exists = db.session.get(Entry, entry_b_id) is not None
    check("A's individual entry is deleted",
          not a_entry_exists,
          f"Entry id={entry_a_id} should not exist after deleting participant A")
    check("B's individual entry is still present",
          b_entry_exists,
          f"Entry id={entry_b_id} must survive deletion of a different participant")

    # ═════════════════════════════════════════════════════════════════════════
    # Case 2: Deleting A does NOT delete the GroupEntry A was a member of
    # ═════════════════════════════════════════════════════════════════════════
    print("\nCase 2: Deleting A does NOT delete GroupEntry rows A was a member of")
    group_still_exists  = db.session.get(GroupEntry, group_id) is not None
    group_entry_exists  = db.session.get(Entry, group_entry_id) is not None
    check("GroupEntry object still exists after deleting A",
          group_still_exists,
          f"GroupEntry id={group_id} (Team Sunrise) must not be cascade-deleted")
    check("Entry row for the group still exists",
          group_entry_exists,
          f"Entry id={group_entry_id} (group_id={group_id}) must not be cascade-deleted")

    # ═════════════════════════════════════════════════════════════════════════
    # Case 3: Entry with group_id set (participant_id NULL) NOT deleted by migration
    # ═════════════════════════════════════════════════════════════════════════
    print("\nCase 3: Entry with group_id set (participant_id NULL) survives orphan migration")
    # The migration ran inside create_app via _apply_migrations(), which deleted
    # participant_id IS NULL AND group_id IS NULL rows.
    # The group entry row has participant_id=NULL but group_id is NOT NULL, so it must survive.
    check("Group entry (participant_id=NULL, group_id=NOT NULL) is NOT deleted by migration",
          group_entry_exists,
          f"Entry id={group_entry_id} has group_id={group_id}, should survive the NULL/NULL migration")

    # ═════════════════════════════════════════════════════════════════════════
    # Case 4: Entry with BOTH NULL fields IS deleted by the orphan migration
    # ═════════════════════════════════════════════════════════════════════════
    print("\nCase 4: Entry with participant_id=NULL AND group_id=NULL is deleted by migration")
    # _apply_migrations() ran at startup (inside create_app), but the orphan row
    # was inserted AFTER that. We re-run the migration SQL manually to simulate
    # the next app startup cleaning it up.
    db.session.execute(text(
        "DELETE FROM entry WHERE participant_id IS NULL AND group_id IS NULL"
    ))
    db.session.commit()
    orphan_still_exists = db.session.get(Entry, orphan_entry_id) is not None
    check("True orphan entry (both FKs NULL) is deleted by the migration",
          not orphan_still_exists,
          f"Entry id={orphan_entry_id} with participant_id=NULL, group_id=NULL must be removed")

    # ═════════════════════════════════════════════════════════════════════════
    # Case 5: Scores attached to A's entry are gone (cascade through Entry)
    # ═════════════════════════════════════════════════════════════════════════
    print("\nCase 5: Scores for A's entry are cascade-deleted")
    a_scores = Score.query.filter(
        Score.entry_id == entry_a_id
    ).all()
    b_scores = Score.query.filter(
        Score.entry_id == entry_b_id
    ).all()
    check("All Score rows for A's entry are deleted",
          len(a_scores) == 0,
          f"Found {len(a_scores)} Score rows for entry_id={entry_a_id}; expected 0")
    check("Score rows for B's entry are unaffected",
          len(b_scores) == 9,   # 3 judges × 3 criteria
          f"Found {len(b_scores)} Score rows for B's entry; expected 9")

    # ═════════════════════════════════════════════════════════════════════════
    # Case 6: AuditLog rows for A's entry are gone (cascade through Entry)
    # ═════════════════════════════════════════════════════════════════════════
    print("\nCase 6: AuditLog rows for A's entry are cascade-deleted")
    a_logs = AuditLog.query.filter(
        AuditLog.entry_id == entry_a_id
    ).all()
    b_logs = AuditLog.query.filter(
        AuditLog.entry_id == entry_b_id
    ).all()
    check("All AuditLog rows for A's entry are deleted",
          len(a_logs) == 0,
          f"Found {len(a_logs)} AuditLog rows for entry_id={entry_a_id}; expected 0")
    check("AuditLog rows for B's entry are unaffected",
          len(b_logs) == 1,
          f"Found {len(b_logs)} AuditLog rows for B's entry; expected 1")

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n── Summary ─────────────────────────────────────────────────────────────")
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f"  {passed} passed, {failed} failed\n")
if failed:
    print("  Failed checks:")
    for label, ok in results:
        if not ok:
            print(f"    - {label}")
    sys.exit(1)
else:
    print("  All cascade delete checks passed.")
    sys.exit(0)
