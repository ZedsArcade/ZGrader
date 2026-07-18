"""Seed data for GradingCompanyToleranceRule -- the config-driven thresholds
behind the multi-company comparison engine (zgrader/analysis/rules_engine.py).

These thresholds are heuristic starting points grounded in each company's
publicly known grading philosophy (see notes per rule), NOT scraped from an
official published tolerance table -- several companies (PSA in particular)
don't publish exact numeric cutoffs. They are deliberately stored as data so
they can be tuned later against real submitted-grade outcomes without
touching analysis code. Treat v1 numbers as a reasonable starting point, not
gospel.

Centering thresholds use metric_key="worse_side_pct": the larger share of a
lr/tb ratio, e.g. 58 for a 58/42 split. Corners/edges/surface use
metric_key="raw_score": the 0-10 analysis score for that category.
"""

from sqlalchemy.orm import Session

from zgrader.models.grading_comparison import GradingCompany, GradingCompanyToleranceRule

_PSA_CENTERING_NOTE = (
    "PSA gives a single holistic grade with no published subgrades and has "
    "historically been more forgiving on centering than BGS/CGC, though "
    "standards tightened after 2020. A {worse_side_pct:.0f}/{better_side_pct:.0f} "
    "split is {severity_word} for PSA."
)
_BGS_CENTERING_NOTE = (
    "BGS prints centering as an explicit subgrade and is widely considered the "
    "strictest of the major companies on centering, especially for a Gem Mint 10 "
    "or Black Label. A {worse_side_pct:.0f}/{better_side_pct:.0f} split is "
    "{severity_word} by BGS's standards."
)
_CGC_CENTERING_NOTE = (
    "CGC has built a reputation for strict, consistent centering grading -- "
    "sometimes called 'the BGS of the CGC era' by collectors. A "
    "{worse_side_pct:.0f}/{better_side_pct:.0f} split is {severity_word} for CGC."
)
_TAG_CENTERING_NOTE = (
    "TAG measures centering with computer vision and reports a precise ratio on "
    "its DIG report rather than relying on visual estimation. A "
    "{worse_side_pct:.0f}/{better_side_pct:.0f} split is {severity_word} under TAG's "
    "measured-tolerance approach."
)

_CATEGORY_NOTE_TEMPLATES = {
    GradingCompany.PSA: (
        "PSA's single holistic grade is often capped by its weakest category; "
        "a {category} score of {raw_score:.1f}/10 is {severity_word} for PSA."
    ),
    GradingCompany.BGS: (
        "BGS prints {category} as its own subgrade, so weaknesses here are called "
        "out explicitly rather than averaged away; {raw_score:.1f}/10 is "
        "{severity_word} for a strong BGS {category} subgrade."
    ),
    GradingCompany.CGC: (
        "CGC's category-level grading is generally strict and consistent; "
        "{raw_score:.1f}/10 on {category} is {severity_word} for CGC."
    ),
    GradingCompany.TAG: (
        "TAG's computer-vision scoring flags {category} defects algorithmically "
        "and consistently; {raw_score:.1f}/10 is {severity_word} under TAG's "
        "DIG+ subscore approach."
    ),
}

TOLERANCE_RULES_SEED: list[dict] = [
    # --- Centering: worse_side_pct thresholds (e.g. 60 == a 60/40 split) ---
    {
        "company": GradingCompany.PSA,
        "category": "centering",
        "metric_key": "worse_side_pct",
        "thresholds": {"minor_at": 60, "major_at": 70},
        "note_template": _PSA_CENTERING_NOTE,
    },
    {
        "company": GradingCompany.BGS,
        "category": "centering",
        "metric_key": "worse_side_pct",
        "thresholds": {"minor_at": 55, "major_at": 60},
        "note_template": _BGS_CENTERING_NOTE,
    },
    {
        "company": GradingCompany.CGC,
        "category": "centering",
        "metric_key": "worse_side_pct",
        "thresholds": {"minor_at": 55, "major_at": 62},
        "note_template": _CGC_CENTERING_NOTE,
    },
    {
        "company": GradingCompany.TAG,
        "category": "centering",
        "metric_key": "worse_side_pct",
        "thresholds": {"minor_at": 57, "major_at": 65},
        "note_template": _TAG_CENTERING_NOTE,
    },
    # --- Corners: raw_score thresholds (10 = pristine, flags below) ---
    {
        "company": GradingCompany.PSA,
        "category": "corners",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 8.5, "major_below": 7.0},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.PSA],
    },
    {
        "company": GradingCompany.BGS,
        "category": "corners",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 9.0, "major_below": 8.0},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.BGS],
    },
    {
        "company": GradingCompany.CGC,
        "category": "corners",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 9.0, "major_below": 8.0},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.CGC],
    },
    {
        "company": GradingCompany.TAG,
        "category": "corners",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 8.7, "major_below": 7.5},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.TAG],
    },
    # --- Edges: raw_score thresholds ---
    {
        "company": GradingCompany.PSA,
        "category": "edges",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 8.5, "major_below": 7.0},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.PSA],
    },
    {
        "company": GradingCompany.BGS,
        "category": "edges",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 9.0, "major_below": 8.0},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.BGS],
    },
    {
        "company": GradingCompany.CGC,
        "category": "edges",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 9.0, "major_below": 8.0},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.CGC],
    },
    {
        "company": GradingCompany.TAG,
        "category": "edges",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 8.7, "major_below": 7.5},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.TAG],
    },
    # --- Surface: raw_score thresholds ---
    {
        "company": GradingCompany.PSA,
        "category": "surface",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 8.5, "major_below": 7.0},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.PSA],
    },
    {
        "company": GradingCompany.BGS,
        "category": "surface",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 8.5, "major_below": 7.5},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.BGS],
    },
    {
        "company": GradingCompany.CGC,
        "category": "surface",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 8.5, "major_below": 7.5},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.CGC],
    },
    {
        "company": GradingCompany.TAG,
        "category": "surface",
        "metric_key": "raw_score",
        "thresholds": {"minor_below": 8.5, "major_below": 7.5},
        "note_template": _CATEGORY_NOTE_TEMPLATES[GradingCompany.TAG],
    },
]


def seed_tolerance_rules(db: Session) -> None:
    existing = {
        (row.company, row.category, row.metric_key)
        for row in db.query(GradingCompanyToleranceRule).all()
    }
    for entry in TOLERANCE_RULES_SEED:
        key = (entry["company"], entry["category"], entry["metric_key"])
        if key in existing:
            continue
        db.add(GradingCompanyToleranceRule(**entry))
    db.commit()
