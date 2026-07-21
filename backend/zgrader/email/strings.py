"""Static text for the notification email templates, in English and Spanish."""

EMAIL_STRINGS = {
    "en": {
        "footer": "This is an automated notification from {business_name}, an independent TCG pre-grading service.",
        "greeting": "Hi,",
        "received_intro": "We've received your submission",
        "received_for": "for",
        "received_body": (
            "Once your card arrives and is scanned, we'll run our automated analysis and "
            "let you know as soon as your report is ready."
        ),
        "published_intro": "Your pre-grade report for submission",
        "published_ready": "is ready",
        "published_body": "Log in to your dashboard to view the scorecard and download the full PDF report.",
        "subject_received": "Submission {submission_code} received",
        "subject_published": "Your report for {submission_code} is ready",
    },
    "es": {
        "footer": "Esta es una notificación automática de {business_name}, un servicio independiente de pre-calificación de TCG.",
        "greeting": "Hola,",
        "received_intro": "Hemos recibido su envío",
        "received_for": "para",
        "received_body": (
            "En cuanto su carta llegue y sea escaneada, ejecutaremos nuestro análisis "
            "automatizado y le avisaremos tan pronto como su informe esté listo."
        ),
        "published_intro": "Su informe de pre-calificación para el envío",
        "published_ready": "ya está listo",
        "published_body": "Inicie sesión en su panel para ver la puntuación y descargar el informe completo en PDF.",
        "subject_received": "Envío {submission_code} recibido",
        "subject_published": "Su informe para {submission_code} ya está listo",
    },
}
