"""
Seed all competition items and judging criteria from the UUKMA Kalamela Manual 2026.
Only runs if the database is empty.
"""
from app import db
from app.models import CompetitionItem, Criteria, EventConfig


def seed_if_empty():
    if CompetitionItem.query.count() > 0:
        return

    # ── Event Config ──────────────────────────────────────────────────
    if EventConfig.query.count() == 0:
        db.session.add(EventConfig())

    # ── Helper ────────────────────────────────────────────────────────
    def add_item(name, category, item_type, duration, min_m=None, max_m=None,
                 gender=None, criteria_list=None):
        item = CompetitionItem(
            name=name,
            category=category,
            item_type=item_type,
            max_duration_mins=duration,
            min_members=min_m,
            max_members=max_m,
            gender_restriction=gender,
            is_custom=False,
        )
        db.session.add(item)
        db.session.flush()
        if criteria_list:
            for order, (cname, cmax) in enumerate(criteria_list):
                db.session.add(Criteria(
                    item_id=item.id,
                    name=cname,
                    max_marks=cmax,
                    display_order=order,
                ))
        return item

    # ── Shared criteria sets ──────────────────────────────────────────
    KIDS_SONG_CRITERIA = [
        ('Memorisation and delivery', 15),
        ('Literary Clarity', 25),
        ('Flow and Expression', 25),
        ('Stage confidence and Presentation', 20),
        ('Overall impression', 15),
    ]

    ELOCUTION_CRITERIA = [
        ('Introduction and speech construction', 15),
        ('Presentation and delivery', 15),
        ('Content of Elocution (relevance to topic)', 30),
        ('Language and vocal inclination', 25),
        ('Stage confidence and Overall impression', 15),
    ]

    POEM_CRITERIA = [
        ('Memorisation and delivery', 15),
        ('Language & Literary Clarity', 30),
        ('Flow and Expression', 30),
        ('Stage confidence and Presentation', 10),
        ('Overall impression', 15),
    ]

    SOLO_SONG_CRITERIA = [
        ('Fluency', 15),
        ('Sruthilayam', 25),
        ('Rhythm & Clarity', 25),
        ('Bhavam, Language & Literary Clarity', 20),
        ('Overall impression', 15),
    ]

    MONOACT_CRITERIA = [
        ('Voice modulation and clarity', 20),
        ('Variety of Characters and acting skills', 30),
        ('Flow and Expression', 20),
        ('Selection of situation', 15),
        ('Stage confidence & Overall impression', 15),
    ]

    CLASSICAL_SOLO_CRITERIA = [
        ('Costume and visual appeal', 10),
        ('Music and choreography', 20),
        ('Movement & Rhythm (Nritta, Nritya, Natya)', 25),
        ('Presentation / Postures & perfection of mudras (Adavu, Mudra, Angasudhi)', 30),
        ('Sense of space & Overall impression', 15),
    ]

    FOLK_DANCE_CRITERIA = [
        ('Costume and visual appeal', 10),
        ('Music and choreography', 25),
        ('Movement & Rhythm', 25),
        ('Expression, power & use of stage', 25),
        ('Overall impression', 15),
    ]

    CINEMATIC_SOLO_CRITERIA = [
        ('Costume and visual appeal', 10),
        ('Music and choreography', 20),
        ('Movement & Rhythm', 25),
        ('Use of stage, Power & dynamics', 25),
        ('Overall impression', 15),
        ('Use of Properties', 5),
    ]

    CINEMATIC_GROUP_CRITERIA = [
        ('Costume and visual appeal', 10),
        ('Music and choreography', 20),
        ('Synchronisation & group formation', 25),
        ('Power & dynamics', 25),
        ('Overall impression', 15),
        ('Use of Properties', 5),
    ]

    CLASSICAL_GROUP_CRITERIA = [
        ('Costume and visual appeal', 10),
        ('Music and choreography', 20),
        ('Movement & Rhythm (Nritta, Nritya, Natya)', 25),
        ('Synchronisation, Postures & perfection of mudras (Adavu, Mudra, Angasudhi)', 30),
        ('Use of stage & Overall impression', 15),
    ]

    GROUP_SONG_CRITERIA = [
        ('Pitch & Modulation', 10),
        ('Sruthilayam', 25),
        ('Rhythm', 25),
        ('Bhavam and Literary Clarity', 25),
        ('Overall impression', 15),
    ]

    NAADAN_CRITERIA = [
        ('Language and Lyrics', 10),
        ('Rhythm & Melody', 20),
        ('Bhavam, Sruthi & Layam', 20),
        ('Team Coordination and presentation', 20),
        ('Cultural Authenticity', 15),
        ('Overall impression', 15),
    ]

    THIRUVATHIRA_CRITERIA = [
        ('Costume and visual appeal', 10),
        ('Music and choreography', 25),
        ('Movement & Rhythm', 25),
        ('Stage use, presentation & synchronisation', 25),
        ('Overall impression', 15),
    ]

    MIME_CRITERIA = [
        ('Costume, visual effect & face makeup', 10),
        ('Expressions and co-ordination', 25),
        ('Creativity & depictions of situation', 25),
        ('Stage use, presentation & subject', 25),
        ('Overall impression', 15),
    ]

    GROUP_DANCE_CRITERIA = [
        ('Choreography and Creativity', 30),
        ('Coordination and Synchronization', 25),
        ('Rhythm, Abhinaya and Bhavam (Expressions)', 25),
        ('Costumes and Make-up', 10),
        ('Overall Impact', 10),
    ]

    # ── KIDS ──────────────────────────────────────────────────────────
    add_item('Solo Song (Malayalam)', 'Kids', 'solo', 5,
             criteria_list=KIDS_SONG_CRITERIA)
    add_item('Story Telling (Malayalam)', 'Kids', 'solo', 4,
             criteria_list=KIDS_SONG_CRITERIA)
    add_item('Cinematic Dance Solo', 'Kids', 'solo', 5,
             criteria_list=CINEMATIC_SOLO_CRITERIA)
    add_item('Group Cinematic Dance', 'Kids', 'group', 7, min_m=3, max_m=8,
             criteria_list=CINEMATIC_GROUP_CRITERIA)

    # ── SUB-JUNIOR ────────────────────────────────────────────────────
    for cat in ['Sub-Junior', 'Junior', 'Senior']:
        add_item('Solo Song (Malayalam Light Music)', cat, 'solo', 5,
                 criteria_list=SOLO_SONG_CRITERIA)
        add_item('Poem Recitation (Malayalam)', cat, 'solo', 5,
                 criteria_list=POEM_CRITERIA)
        add_item('Monoact (Malayalam)', cat, 'solo', 5,
                 criteria_list=MONOACT_CRITERIA)
        add_item('Elocution (English)', cat, 'solo', 5,
                 criteria_list=ELOCUTION_CRITERIA)
        add_item('Elocution (Malayalam)', cat, 'solo', 5,
                 criteria_list=ELOCUTION_CRITERIA)
        add_item('Cinematic Dance Solo', cat, 'solo', 5,
                 criteria_list=CINEMATIC_SOLO_CRITERIA)
        add_item('Folk Dance', cat, 'solo', 7,
                 criteria_list=FOLK_DANCE_CRITERIA)
        add_item('Bharathanatyam', cat, 'solo', 10,
                 criteria_list=CLASSICAL_SOLO_CRITERIA)
        add_item('Mohiniyattom', cat, 'solo', 10,
                 criteria_list=CLASSICAL_SOLO_CRITERIA)
        add_item('Group Classical Dance', cat, 'group', 10, min_m=3, max_m=8,
                 criteria_list=CLASSICAL_GROUP_CRITERIA)
        add_item('Group Cinematic Dance', cat, 'group', 7, min_m=3, max_m=8,
                 criteria_list=CINEMATIC_GROUP_CRITERIA)

    # ── SUPER SENIOR ──────────────────────────────────────────────────
    add_item('Solo Song (Malayalam Light Music)', 'Super Senior', 'solo', 5,
             criteria_list=SOLO_SONG_CRITERIA)
    add_item('Group Cinematic Dance', 'Super Senior', 'group', 7, min_m=3, max_m=8,
             criteria_list=CINEMATIC_GROUP_CRITERIA)
    add_item('Group Dance / Sanga Nritham', 'Super Senior', 'group', 10, min_m=3, max_m=8,
             criteria_list=GROUP_DANCE_CRITERIA)

    # ── COMMON ────────────────────────────────────────────────────────
    add_item('Mime', 'Common', 'group', 5, min_m=4, max_m=6,
             criteria_list=MIME_CRITERIA)
    add_item('Group Song', 'Common', 'group', 5, min_m=3, max_m=10,
             criteria_list=GROUP_SONG_CRITERIA)
    add_item('Thiruvathira', 'Common', 'group', 10, max_m=10, gender='Female',
             criteria_list=THIRUVATHIRA_CRITERIA)
    add_item('Oppana', 'Common', 'group', 10, max_m=10, gender='Female',
             criteria_list=THIRUVATHIRA_CRITERIA)
    add_item('Margamkali', 'Common', 'group', 10, max_m=10, gender='Female',
             criteria_list=THIRUVATHIRA_CRITERIA)
    add_item('Naadan Pattukal (Folk Song)', 'Common', 'group', 5, min_m=3, max_m=10,
             criteria_list=NAADAN_CRITERIA)

    db.session.commit()
