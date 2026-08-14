"""Renders a submission's analysis results into a branded PDF report via
Jinja2 (templates/report.html.jinja) + WeasyPrint.
"""

import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from zgrader.analysis import recompute
from zgrader.config import config
from zgrader.models import AnalysisSide, GradingCompany, Report, ReportStatus, Settings, Submission
from zgrader.reports.strings import (
    CATEGORY_LABELS,
    LIMITATION_LABELS,
    REGION_LOCATION_LABELS,
    REPORT_STRINGS,
    SEVERITY_LABELS,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
CATEGORY_ORDER = ["centering", "corners", "edges", "surface"]
_SEVERITY_SORT_RANK = {"major": 0, "minor": 1, "none": 2}


def _file_uri(path: str | None) -> str:
    if not path:
        return ""
    return Path(path).resolve().as_uri()


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "jinja"]),
)
_env.filters["file_uri"] = _file_uri


def _severity_rank(severity) -> int:
    value = severity.value if hasattr(severity, "value") else severity
    return _SEVERITY_SORT_RANK.get(value, 99)


# Region ids that are index-based rather than named locations. Both live
# under the surface category (creases ride along with surface's regions, see
# analysis/pipeline.py) and both need a numbered label -- without an entry
# here a dismissed crease printed its raw id, "crease_0", in both languages.
_INDEXED_REGION_LABELS = {"blob_": "surface_finding_label", "crease_": "crease_finding_label"}


def _region_location(category: str, region_id: str, language: str) -> str:
    if category == "surface":
        for prefix, string_key in _INDEXED_REGION_LABELS.items():
            if region_id.startswith(prefix):
                try:
                    n = int(region_id.split("_", 1)[1]) + 1
                except (ValueError, IndexError):
                    n = region_id
                return REPORT_STRINGS[language][string_key].format(n=n)
    return REGION_LOCATION_LABELS[language].get(region_id, region_id)


def _build_dismissed_findings(submission, language: str) -> list[dict]:
    """Itemise every client-dismissed finding (side, category, human
    location, and the original finding note) by resolving each
    dismissed_regions key against the stored per-side regions -- powers the
    report's transparent 'Client Adjustments' section."""
    keys = submission.dismissed_regions or []
    if not keys:
        return []

    region_index: dict[tuple[str, str, str], dict] = {}
    for result in submission.analysis_results:
        if result.side == AnalysisSide.combined:
            continue
        side = result.side.value
        category = result.category.value if hasattr(result.category, "value") else str(result.category)
        for region in (result.measurements or {}).get("regions", []):
            region_index[(side, category, region["id"])] = region

    labels = CATEGORY_LABELS[language]
    findings = []
    for key in keys:
        parts = key.split(":")
        if len(parts) != 3:
            continue
        side, category, region_id = parts
        region = region_index.get((side, category, region_id))
        findings.append(
            {
                "side": side,
                "category_label": labels.get(category, category),
                "location": _region_location(category, region_id, language),
                "note": (region or {}).get("note"),
            }
        )
    return findings


def build_report_context(submission: Submission, settings: Settings) -> dict:
    card = submission.card
    # Resolved up here because the scorecard loop below needs it to turn
    # limitation codes into sentences.
    language = submission.language.value

    combined_by_category: dict[str, object] = {}
    per_side_by_category: dict[str, dict] = {}
    for result in submission.analysis_results:
        if result.side == AnalysisSide.combined:
            combined_by_category[result.category] = result
        else:
            per_side_by_category.setdefault(result.category, {})[result.side] = result

    scorecard = []
    lower_confidence_categories = []
    for category in CATEGORY_ORDER:
        combined = combined_by_category.get(category)
        sides = per_side_by_category.get(category, {})
        front = sides.get(AnalysisSide.front)
        back = sides.get(AnalysisSide.back)
        if combined and combined.flags.get("lower_confidence"):
            lower_confidence_categories.append(category)
        # None when unmeasurable as well as when the row is absent. The
        # template already renders an em dash for a missing score, so both
        # read as "no number" rather than as zero.
        combined_score = (
            float(combined.raw_score)
            if combined is not None and combined.raw_score is not None
            else None
        )
        # Pristine auto-detected score, stashed by pipeline._persist_combined
        # -- shown struck-through beside the adjusted score when the client
        # dismissed findings that changed this category.
        # What constrained this category, resolved from codes to sentences at
        # render time so the report can be produced in either language.
        block = (combined.measurements or {}).get("assessment") if combined else None
        limitation_notes = [
            LIMITATION_LABELS[language][code]
            for code in (block or {}).get("limitations", [])
            if code in LIMITATION_LABELS[language]
        ]
        confidence = (block or {}).get("confidence")
        unmeasurable = bool(block) and block.get("state") != "measured"

        original = (combined.measurements or {}).get("original_raw_score") if combined else None
        original_score = float(original) if original is not None else None
        scorecard.append(
            {
                "category": category,
                "combined_score": combined_score,
                "original_combined_score": original_score,
                "adjusted": original_score is not None
                and combined_score is not None
                and round(original_score, 2) != round(combined_score, 2),
                "confidence": confidence,
                "unmeasurable": unmeasurable,
                "limitation_notes": limitation_notes,
                "front_score": float(front.raw_score) if front and front.raw_score is not None else None,
                "back_score": float(back.raw_score) if back and back.raw_score is not None else None,
                "front_image": front.annotated_image_path if front else None,
                "back_image": back.annotated_image_path if back else None,
            }
        )

    comparisons_by_category: dict[str, list] = {}
    for comp in submission.company_comparisons:
        comparisons_by_category.setdefault(comp.category, []).append(comp)
    for comparisons in comparisons_by_category.values():
        comparisons.sort(key=lambda c: (_severity_rank(c.severity), c.company.value))

    dismissed_findings = _build_dismissed_findings(submission, language)
    return {
        "strings": REPORT_STRINGS[language],
        "category_labels": CATEGORY_LABELS[language],
        "severity_labels": SEVERITY_LABELS[language],
        "business": {
            "name": settings.business_name,
            "logo_path": settings.business_logo_path,
            "contact": settings.business_contact,
        },
        "disclaimer": settings.disclaimer_text,
        "submission": {
            "code": submission.submission_code,
            "created_at": submission.created_at,
            "client_email": submission.user.email if submission.user else None,
        },
        "card": {
            "game": card.game if card else None,
            "set_name": card.set_name if card else None,
            "card_name": card.card_name if card else None,
            "card_number": card.card_number if card else None,
            "foil": card.foil if card else False,
        },
        "scorecard": scorecard,
        "comparisons_by_category": comparisons_by_category,
        "companies": [c.value for c in GradingCompany],
        "lower_confidence_categories": lower_confidence_categories,
        "client_adjusted": bool(dismissed_findings),
        "dismissed_count": len(dismissed_findings),
        "dismissed_findings": dismissed_findings,
        "generated_at": datetime.datetime.now(datetime.timezone.utc),
        # Printed in the footer so a forwarded copy of this PDF carries a
        # route back to how its numbers were produced.
        "methodology_url": f"{config.site_url.rstrip('/')}/methodology",
    }


def render_html(context: dict) -> str:
    template = _env.get_template("report.html.jinja")
    return template.render(**context)


def build_pdf(context: dict, output_path: Path) -> Path:
    # Imported here rather than at module scope, the same way ai.py defers
    # httpx. WeasyPrint renders through Pango/Cairo, which are system
    # libraries rather than part of the wheel -- so importing it at module
    # scope made this module, and everything that reaches it (the submissions
    # router, the watcher, and nine test modules through them), unimportable
    # anywhere those libraries are absent. Deferring it means only the code
    # path that actually renders a PDF needs them, which is also why the API
    # process no longer loads Pango at startup.
    from weasyprint import HTML

    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_str = render_html(context)
    HTML(string=html_str, base_url=str(TEMPLATES_DIR)).write_pdf(str(output_path))
    return output_path


def generate_report(db: Session, submission: Submission) -> Report:
    settings = db.query(Settings).first()
    if settings is None:
        raise RuntimeError("No Settings row found -- run zgrader.seed.seed_all() first")

    # The overlays are drawn at analysis time from the detected border, and a
    # client centering adjustment moves the score without moving the drawing.
    # Redrawn here rather than on every apply: this is the moment the picture
    # becomes a published document, and it is already the slow path.
    recompute.redraw_centering_annotations(db, submission)

    context = build_report_context(submission, settings)

    existing_versions = [r.version for r in submission.reports]
    version = max(existing_versions, default=0) + 1

    reports_dir = Path(config.reports_dir) / submission.submission_code
    # Even the saved filename is labelled when the client adjusted the
    # assessment, so an adjusted report can't be mistaken for a pristine one.
    suffix = "_client_adjusted" if context["client_adjusted"] else ""
    pdf_path = reports_dir / f"report_v{version}{suffix}.pdf"
    build_pdf(context, pdf_path)

    report = Report(
        submission_id=submission.id,
        version=version,
        status=ReportStatus.draft,
        pdf_path=str(pdf_path),
        generated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(report)
    db.flush()
    return report
