"""Renders a submission's analysis results into a branded PDF report via
Jinja2 (templates/report.html.jinja) + WeasyPrint.
"""

import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from weasyprint import HTML

from zgrader.config import config
from zgrader.models import AnalysisSide, GradingCompany, Report, ReportStatus, Settings, Submission
from zgrader.reports.strings import CATEGORY_LABELS, REPORT_STRINGS, SEVERITY_LABELS

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


def build_report_context(submission: Submission, settings: Settings) -> dict:
    card = submission.card

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
        scorecard.append(
            {
                "category": category,
                "combined_score": float(combined.raw_score) if combined else None,
                "front_score": float(front.raw_score) if front else None,
                "back_score": float(back.raw_score) if back else None,
                "front_image": front.annotated_image_path if front else None,
                "back_image": back.annotated_image_path if back else None,
            }
        )

    comparisons_by_category: dict[str, list] = {}
    for comp in submission.company_comparisons:
        comparisons_by_category.setdefault(comp.category, []).append(comp)
    for comparisons in comparisons_by_category.values():
        comparisons.sort(key=lambda c: (_severity_rank(c.severity), c.company.value))

    language = submission.language.value
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
        "generated_at": datetime.datetime.now(datetime.timezone.utc),
    }


def render_html(context: dict) -> str:
    template = _env.get_template("report.html.jinja")
    return template.render(**context)


def build_pdf(context: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_str = render_html(context)
    HTML(string=html_str, base_url=str(TEMPLATES_DIR)).write_pdf(str(output_path))
    return output_path


def generate_report(db: Session, submission: Submission) -> Report:
    settings = db.query(Settings).first()
    if settings is None:
        raise RuntimeError("No Settings row found -- run zgrader.seed.seed_all() first")

    context = build_report_context(submission, settings)

    existing_versions = [r.version for r in submission.reports]
    version = max(existing_versions, default=0) + 1

    reports_dir = Path(config.reports_dir) / submission.submission_code
    pdf_path = reports_dir / f"report_v{version}.pdf"
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
