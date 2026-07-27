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
        # -- Account emails ------------------------------------------------
        "ignore_if_not_you": "If this wasn't you, you can safely ignore this email -- nothing has changed.",
        "subject_verify": "Confirm your email address",
        "verify_intro": "Please confirm your email address to finish setting up your account.",
        "verify_action": "Confirm my email",
        "verify_expiry": "This link expires in 24 hours.",
        "subject_reset": "Reset your password",
        "reset_intro": "We received a request to reset the password on your account.",
        "reset_action": "Choose a new password",
        "reset_expiry": "This link expires in 1 hour and can only be used once.",
        "subject_already_registered": "You already have an account",
        "already_registered_intro": (
            "Someone tried to create an account with this email address, but one already "
            "exists. If that was you, sign in instead -- or reset your password if you've "
            "forgotten it."
        ),
        "already_registered_action": "Sign in",
        "already_registered_expiry": "",
        "subject_password_changed": "Your password was changed",
        "password_changed_intro": (
            "The password on your account was just changed, and you've been signed out "
            "everywhere else. If you didn't do this, reset your password immediately."
        ),
        "password_changed_action": "Reset my password",
        "password_changed_expiry": "",
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
        # -- Correos de cuenta ---------------------------------------------
        "ignore_if_not_you": "Si no ha sido usted, puede ignorar este correo: no se ha modificado nada.",
        "subject_verify": "Confirme su dirección de correo",
        "verify_intro": "Confirme su dirección de correo para terminar de configurar su cuenta.",
        "verify_action": "Confirmar mi correo",
        "verify_expiry": "Este enlace caduca en 24 horas.",
        "subject_reset": "Restablezca su contraseña",
        "reset_intro": "Hemos recibido una solicitud para restablecer la contraseña de su cuenta.",
        "reset_action": "Elegir una contraseña nueva",
        "reset_expiry": "Este enlace caduca en 1 hora y solo puede usarse una vez.",
        "subject_already_registered": "Ya tiene una cuenta",
        "already_registered_intro": (
            "Alguien ha intentado crear una cuenta con esta dirección de correo, pero ya "
            "existe una. Si ha sido usted, inicie sesión, o restablezca su contraseña si "
            "la ha olvidado."
        ),
        "already_registered_action": "Iniciar sesión",
        "already_registered_expiry": "",
        "subject_password_changed": "Su contraseña ha cambiado",
        "password_changed_intro": (
            "La contraseña de su cuenta acaba de cambiar y se ha cerrado la sesión en el "
            "resto de dispositivos. Si no ha sido usted, restablezca su contraseña de "
            "inmediato."
        ),
        "password_changed_action": "Restablecer mi contraseña",
        "password_changed_expiry": "",
    },
}
