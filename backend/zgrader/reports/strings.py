"""Static text for the PDF report template, in English and Spanish.

Only the template's own chrome (headers, labels, boilerplate) is
translated here -- data-driven text (card name, business info, the
operator-authored disclaimer, and the rules engine's generated
contention notes) is rendered as stored, since those aren't single-source
strings this module can translate on their behalf.
"""

REPORT_STRINGS = {
    "en": {
        "report_title": "Pre-Grade Report",
        "submission_label": "Submission:",
        "date_label": "Date:",
        "client_label": "Client:",
        "foil_suffix": "(Foil)",
        "scorecard_title": "Summary Scorecard",
        "scorecard_note": "(independent estimate, not a guaranteed grade)",
        "col_category": "Category",
        "col_front": "Front",
        "col_back": "Back",
        "col_combined": "Combined",
        "lower_confidence_badge": "lower confidence",
        "annotated_scans_title": "Annotated Scans",
        "front_caption": "Front",
        "back_caption": "Back",
        "comparison_title": "Multi-Company Comparison",
        "comparison_intro": (
            "This table highlights points of contention that may affect how different grading "
            "companies would treat this card. It intentionally does not predict a specific "
            "numeric grade from any company."
        ),
        "col_company": "Company",
        "col_assessment": "Assessment",
        "col_notes": "Notes",
        "limitations_title": "Limitations & Methodology",
        "limitation_1": (
            "This is an independent pre-grade estimate produced by an automated image-analysis "
            "pipeline. It is not affiliated with, endorsed by, or a guarantee of the outcome from "
            "PSA, Beckett Grading Services (BGS), CGC, TAG, or any other third-party grading company."
        ),
        "limitation_2": (
            "Measurements are derived from flatbed scans. Surface analysis in particular is "
            "lower-confidence: flatbed scanning uses diffuse light, not the raking/angled light "
            "professional graders use to catch surface scratches and print lines, so some surface "
            "defects may be under-detected."
        ),
        "limitation_3": (
            "Company comparison thresholds are heuristic estimates based on each company's "
            "publicly known grading philosophy, not official published tolerance tables, and are "
            "refined over time against real submitted-grade outcomes."
        ),
        "generated_label": "Report generated",
    },
    "es": {
        "report_title": "Informe de Pre-Calificación",
        "submission_label": "Envío:",
        "date_label": "Fecha:",
        "client_label": "Cliente:",
        "foil_suffix": "(Foil)",
        "scorecard_title": "Resumen de Puntuación",
        "scorecard_note": "(estimación independiente, no es una calificación garantizada)",
        "col_category": "Categoría",
        "col_front": "Frente",
        "col_back": "Reverso",
        "col_combined": "Combinado",
        "lower_confidence_badge": "menor confiabilidad",
        "annotated_scans_title": "Escaneos Anotados",
        "front_caption": "Frente",
        "back_caption": "Reverso",
        "comparison_title": "Comparación entre Compañías",
        "comparison_intro": (
            "Esta tabla destaca los puntos de discrepancia que podrían afectar cómo distintas "
            "compañías de calificación tratarían esta carta. Intencionalmente no predice una "
            "calificación numérica específica de ninguna compañía."
        ),
        "col_company": "Compañía",
        "col_assessment": "Evaluación",
        "col_notes": "Notas",
        "limitations_title": "Limitaciones y Metodología",
        "limitation_1": (
            "Esta es una estimación independiente de pre-calificación producida por un proceso "
            "automatizado de análisis de imágenes. No está afiliada, respaldada ni garantiza el "
            "resultado de PSA, Beckett Grading Services (BGS), CGC, TAG ni ninguna otra compañía "
            "de calificación externa."
        ),
        "limitation_2": (
            "Las mediciones se derivan de escaneos planos. El análisis de superficie en particular "
            "tiene menor confiabilidad: el escaneo plano utiliza luz difusa, no la luz rasante/angular "
            "que usan los calificadores profesionales para detectar rayones y líneas de impresión en "
            "la superficie, por lo que algunos defectos de superficie podrían estar subdetectados."
        ),
        "limitation_3": (
            "Los umbrales de comparación entre compañías son estimaciones heurísticas basadas en la "
            "filosofía de calificación públicamente conocida de cada compañía, no en tablas de "
            "tolerancia oficialmente publicadas, y se refinan con el tiempo contra resultados reales "
            "de calificaciones enviadas."
        ),
        "generated_label": "Informe generado",
    },
}

CATEGORY_LABELS = {
    "en": {
        "centering": "Centering",
        "corners": "Corners",
        "edges": "Edges",
        "surface": "Surface",
    },
    "es": {
        "centering": "Centrado",
        "corners": "Esquinas",
        "edges": "Bordes",
        "surface": "Superficie",
    },
}

SEVERITY_LABELS = {
    "en": {
        "none": "None",
        "minor": "Minor",
        "major": "Major",
    },
    "es": {
        "none": "Ninguna",
        "minor": "Menor",
        "major": "Mayor",
    },
}
