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
            "PSA, Beckett Grading Services (BGS), CGC, TAG, ACE, or any other third-party "
            "grading company."
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
        # This PDF gets forwarded to buyers, shops and other collectors, so it
        # should carry a pointer to how its numbers were arrived at rather
        # than leaving a second-hand reader with a score and no working.
        "methodology_label": "Full methodology:",
        "adjusted_watermark": "CLIENT-ADJUSTED",
        "adjusted_title_suffix": "(Client-Adjusted)",
        "adjusted_banner": (
            "⚠ THIS ASSESSMENT WAS ADJUSTED BY THE CLIENT. {count} auto-detected finding(s) were "
            "dismissed at the client's request; the scores below reflect those manual changes, not "
            "the unaltered automated analysis."
        ),
        "adjusted_original_prefix": "was",
        "adjustments_title": "Client Adjustments",
        "adjustments_intro": (
            "The following auto-detected findings were dismissed by the client and are excluded "
            "from the scores above:"
        ),
        "adjusted_disclaimer": (
            "IMPORTANT: This assessment was modified by the client, who dismissed one or more "
            "auto-detected findings. It does not represent the unaltered output of the automated "
            "analysis."
        ),
        "unmeasurable": "Not measurable",
        "surface_finding_label": "surface finding #{n}",
        "crease_finding_label": "possible crease #{n}",
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
            "resultado de PSA, Beckett Grading Services (BGS), CGC, TAG, ACE ni ninguna otra "
            "compañía de calificación externa."
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
        "methodology_label": "Metodología completa:",
        "adjusted_watermark": "AJUSTADO POR EL CLIENTE",
        "adjusted_title_suffix": "(Ajustado por el Cliente)",
        "adjusted_banner": (
            "⚠ ESTA EVALUACIÓN FUE AJUSTADA POR EL CLIENTE. El cliente descartó {count} hallazgo(s) "
            "detectado(s) automáticamente; las puntuaciones a continuación reflejan esos cambios "
            "manuales, no el análisis automatizado sin alterar."
        ),
        "adjusted_original_prefix": "era",
        "adjustments_title": "Ajustes del Cliente",
        "adjustments_intro": (
            "El cliente descartó los siguientes hallazgos detectados automáticamente, que quedan "
            "excluidos de las puntuaciones anteriores:"
        ),
        "adjusted_disclaimer": (
            "IMPORTANTE: Esta evaluación fue modificada por el cliente, quien descartó uno o más "
            "hallazgos detectados automáticamente. No representa el resultado sin alterar del "
            "análisis automatizado."
        ),
        "unmeasurable": "No medible",
        "surface_finding_label": "hallazgo de superficie n.º {n}",
        "crease_finding_label": "posible pliegue n.º {n}",
    },
}


# What constrained a reading, per language, keyed by the codes in
# analysis/assessment.py. Stored as codes rather than sentences precisely so
# this wording can change without re-analysing anything -- and so a card
# analysed in one language can be reported in the other.
#
# A code with no entry here would render as a raw identifier to a customer, so
# adding one in assessment.py means adding copy in both dicts below.
LIMITATION_LABELS = {
    "en": {
        "surface_diffuse_light": (
            "Surface was lit evenly rather than at an angle, so faint scratches and "
            "print lines can be missed."
        ),
        "corners_whitening_only": (
            "Corners were assessed for discolouration only. Material loss — a rounded "
            "or knocked corner that has not changed colour — is not measured."
        ),
        "corners_pale_border": (
            "This card's border is pale, and corner wear is detected as a loss of "
            "colour, so there is little for it to show up against."
        ),
        "centering_no_frame": (
            "No clear printed border was found to measure against, which is normal on "
            "full-art cards where the artwork runs to the edge."
        ),
        "edges_partial": "Some edges could not be sampled and were left out of this score.",
    },
    "es": {
        "surface_diffuse_light": (
            "La superficie se iluminó de forma uniforme y no en ángulo, así que pueden "
            "pasarse por alto arañazos finos y líneas de impresión."
        ),
        "corners_whitening_only": (
            "Las esquinas se evaluaron solo por decoloración. La pérdida de material "
            "—una esquina redondeada o aplastada que no ha cambiado de color— no se mide."
        ),
        "corners_pale_border": (
            "El borde de esta carta es pálido, y el desgaste de esquinas se detecta como "
            "pérdida de color, así que hay poco contraste sobre el que aparezca."
        ),
        "centering_no_frame": (
            "No se encontró un borde impreso claro con el que medir, algo normal en "
            "cartas de ilustración completa donde el arte llega hasta el filo."
        ),
        "edges_partial": "Algunos bordes no pudieron muestrearse y quedaron fuera de esta puntuación.",
    },
}


# Human-readable location for a dismissed region, per language (surface uses
# the "surface_finding_label" template above since it's index-based).
REGION_LOCATION_LABELS = {
    "en": {
        "top_left": "top-left corner",
        "top_right": "top-right corner",
        "bottom_left": "bottom-left corner",
        "bottom_right": "bottom-right corner",
        "top": "top edge",
        "bottom": "bottom edge",
        "left": "left edge",
        "right": "right edge",
        "frame": "centering",
    },
    "es": {
        "top_left": "esquina superior izquierda",
        "top_right": "esquina superior derecha",
        "bottom_left": "esquina inferior izquierda",
        "bottom_right": "esquina inferior derecha",
        "top": "borde superior",
        "bottom": "borde inferior",
        "left": "borde izquierdo",
        "right": "borde derecho",
        "frame": "centrado",
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
