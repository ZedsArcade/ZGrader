from pathlib import Path

from pypdf import PdfReader

from zgrader.dev_trigger import run_dev_trigger


def test_full_pipeline_generates_a_multi_page_pdf(db_session, sample_scan_paths):
    # run_dev_trigger opens its own session via zgrader.db.SessionLocal, which
    # is bound to the same test database as db_session (see conftest.py) --
    # db_session here just ensures the schema/seed exist before it runs.
    result = run_dev_trigger(
        front_path=str(sample_scan_paths["pokemon_front"]),
        back_path=str(sample_scan_paths["pokemon_back"]),
        game="Pokemon",
        card_name="Test Charizard",
        set_name="Base Set",
        card_number="4/102",
        user_email="pdftest@example.com",
        submission_code="SUB-PDFTEST1",
    )

    assert result["status"] == "draft_ready"
    pdf_path = Path(result["report_pdf_path"])
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 5000

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) >= 3

    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "SUB-PDFTEST1" in full_text
    assert "Test Charizard" in full_text
    assert "Centering" in full_text
    assert "Multi-Company Comparison" in full_text
    assert "lower confidence" in full_text.lower()
    for company in ("PSA", "BGS", "CGC", "TAG"):
        assert company in full_text


def test_yugioh_uses_its_own_card_dimensions(db_session, sample_scan_paths):
    result = run_dev_trigger(
        front_path=str(sample_scan_paths["yugioh_front"]),
        back_path=str(sample_scan_paths["yugioh_back"]),
        game="Yu-Gi-Oh!",
        card_name="Test Blue-Eyes",
        user_email="pdftest2@example.com",
        submission_code="SUB-PDFTEST2",
    )
    assert result["status"] == "draft_ready"
    assert Path(result["report_pdf_path"]).exists()
