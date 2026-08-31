import type { Dictionary } from "./en";

export const es: Dictionary = {
  common: {
    retry: "Reintentar",
  },
  nav: {
    admin: "Administración",
    dashboard: "Panel",
    account: "Cuenta",
    logout: "Cerrar sesión",
    login: "Iniciar sesión",
    register: "Registrarse",
    menu: "Menú",
    openMenu: "Abrir menú",
    closeMenu: "Cerrar menú",
    about: "Nosotros",
    services: "Servicios",
    pricing: "Precios",
    howItWorks: "Cómo funciona",
    methodology: "Metodología",
    contact: "Contacto",
    terms: "Términos",
    privacy: "Privacidad",
    refunds: "Reembolsos",
  },
  status: {
    created: "Creado",
    awaiting_scans: "Esperando escaneos",
    processing: "Procesando",
    draft_ready: "Borrador listo",
    approved: "Aprobado",
    published: "Publicado",
    error: "Error",
  },
  category: {
    centering: "Centrado",
    corners: "Esquinas",
    edges: "Bordes",
    surface: "Superficie",
  },
  severity: {
    none: "Ninguna",
    minor: "Menor",
    major: "Mayor",
  },
  landing: {
    title: "Sepa antes de enviar.",
    subtitle:
      "{businessName} es un servicio independiente de pre-calificación para juegos de cartas coleccionables. Envíenos sus cartas y analizaremos el centrado, las esquinas, los bordes y la superficie, para mostrarle exactamente cómo es probable que {companies} traten cada una antes de que pague por un envío real.",
    getStarted: "Comenzar",
    login: "Iniciar sesión",
    feature1Title: "Análisis automatizado",
    feature1Body:
      "Cada envío recibe una medición del centrado, detección de desgaste en esquinas y bordes, y un análisis de textura de superficie, con imágenes anotadas que muestran exactamente lo que se detectó.",
    feature2Title: "Comparación entre compañías",
    feature2Body:
      "{companies} no califican de la misma manera. Destacamos los puntos específicos de discrepancia que podrían influir en el trato de su carta en cada compañía, sin prometer nunca una calificación numérica.",
    feature3Title: "Siga cada envío",
    feature3Body:
      "Cree un envío, mándenos su carta y véala avanzar desde la recepción hasta un informe descargable, todo desde su panel.",
    companiesFallback: "las principales compañías de calificación",
    noteTitle: "Nota importante",
    noteBody:
      "{businessName} es una estimación independiente, no está afiliada, respaldada ni garantiza el resultado de PSA, Beckett Grading Services (BGS), CGC, TAG, ACE ni ninguna otra compañía de calificación externa. Los escaneos se capturan con un escáner plano, que utiliza luz difusa en lugar de luz rasante; el análisis de superficie en particular tiene menor confiabilidad que lo que puede detectar la fotografía especializada de una compañía de calificación.",
  },
  login: {
    title: "Iniciar sesión",
    email: "Correo electrónico",
    password: "Contraseña",
    submit: "Iniciar sesión",
    submitting: "Iniciando sesión…",
    failed: "Error al iniciar sesión",
    forgotPassword: "¿Ha olvidado su contraseña?",
  },
  register: {
    title: "Crear una cuenta",
    subtitle: "Regístrese para enviar cartas y seguir sus informes.",
    email: "Correo electrónico",
    password: "Contraseña",
    passwordHint: "Al menos 8 caracteres.",
    submit: "Registrarse",
    submitting: "Creando cuenta…",
    failed: "Error al registrarse",
    acceptTerms: "Acepto los Términos y condiciones y la Política de privacidad",
    acceptTermsRequired: "Debe aceptar los términos para crear una cuenta.",
    termsLink: "Términos y condiciones",
    privacyLink: "Política de privacidad",
    marketingOptIn: "Envíenme novedades ocasionales sobre nuevos servicios (opcional)",
    checkInbox:
      "Revise su bandeja de entrada: le hemos enviado un enlace para confirmar su correo. Lo necesitará antes de poder enviar una carta.",
  },
  verify: {
    title: "Verificación de correo electrónico",
    verifying: "Verificando…",
    success: "Su correo electrónico ha sido verificado. Ahora puede",
    loginLink: "iniciar sesión",
    failed: "Error de verificación",
  },
  dashboard: {
    title: "Sus envíos",
    subtitle: "Siga cada carta que ha enviado para pre-calificación.",
    newSubmission: "Nuevo envío",
    loadFailed: "Error al cargar los envíos",
    emptyTitle: "Aún no hay cartas calificadas",
    emptyDescription: "Siga aquí cada carta que ha enviado para pre-calificación.",
    emptyCta: "Escanee su primera carta",
    colCode: "Código",
    colStatus: "Estado",
    colCreated: "Creado",
    view: "Ver",
  },
  newSubmission: {
    title: "Nuevo envío",
    subtitle: "Cuéntenos sobre la carta y luego envíenosla para escanearla.",
    game: "Juego",
    dimensionsUnverified: " (dimensiones no verificadas)",
    cardName: "Nombre de la carta",
    setName: "Edición (opcional)",
    cardNumber: "Número de carta (opcional)",
    foil: "Foil / holográfica",
    submit: "Crear envío",
    submitting: "Creando…",
    failed: "Error al crear el envío",
    gamesLoadFailed: "Error al cargar los juegos",
  },
  submissionDetail: {
    createdOn: "Creado",
    download: "Descargar informe",
    downloading: "Descargando…",
    downloadFailed: "El informe aún no está disponible",
    loadFailed: "Error al cargar el envío",
    unknownCard: "Carta desconocida",
    foilLabel: "Foil",
    lowerConfidence: "menor confiabilidad",
    leftRightShort: "I/D",
    topBottomShort: "A/B",
    unmeasurable: "No medible",
    limitation: {
      card_is_foil:
        "Nos indicó que esta carta es foil u holográfica, lo que interfiere con todas las mediciones, así que todas se mantienen en un rango más amplio.",
      surface_no_detail:
        "Esta foto no conserva detalle fino en la cara de la carta, así que un arañazo tampoco habría aparecido: la superficie no se puntuó.",
      surface_diffuse_light:
        "Iluminada de forma uniforme y no en ángulo, así que pueden pasarse por alto arañazos finos.",
      corners_whitening_only:
        "No se pudo establecer el contorno de la carta, así que solo se comprobó la decoloración: una esquina desgastada pero sin decolorar no se detecta.",
      corners_pale_border:
        "Este borde es pálido, así que la mitad del análisis basada en el color tiene poco con lo que trabajar. El material que falta sí se mide.",
      centering_no_frame:
        "No hay un borde impreso claro con el que medir: normal en cartas de ilustración completa.",
      centering_partial_frame:
        "Se encontró borde impreso en algunos lados pero no en todos, así que esto se apoya en menos filos de lo habitual.",
      edges_partial: "Algunos bordes no pudieron muestrearse y quedaron fuera de esta puntuación.",
      edges_thin_border:
        "El borde de esta carta es demasiado estrecho para muestrear cartón limpio junto al filo, así que esos lados se juzgaron solo por la rectitud del corte.",
      capture_too_low_resolution:
        "La carta es demasiado pequeña en esta foto para que el desgaste a esta escala sea visible: una foto más cercana permitiría medirlo.",
      capture_modest_resolution:
        "Ocupa lo suficiente para mostrar daños evidentes, no para juzgar el desgaste fino, así que esta lectura se mantiene en un rango más amplio.",
      // Mismo motivo que en en.ts: la segunda frase es para los 2 de cada 10
      // casos que un recorte nuevo no puede salvar.
      geometry_unverified:
        "No se pudieron localizar los bordes de la carta en esta imagen, así que no había nada fiable desde donde medir. Normalmente es el recorte: arrastre los tiradores para que ciñan la carta, sin fondo dentro de ellos, y envíe de nuevo. Si aun así no funciona, es probable que la carta y la superficie de detrás tuvieran tonos demasiado parecidos: vuelva a fotografiarla sobre un fondo liso que contraste con la carta.",
      geometry_aspect_mismatch:
        "El área medida no tiene la forma de una carta, así que las cifras en milímetros están mal escaladas en al menos un eje.",
      combined_single_side:
        "Solo se pudo leer una cara para esta categoría, así que esto se apoya únicamente en esa cara y no en ambas: una visión más limitada de la carta, no una peor.",
    },
    comparisonTitle: "Comparación entre compañías",
    comparisonSubtitle:
      "Puntos de discrepancia que podrían afectar cómo cada compañía trata esta carta. Esto no es una calificación numérica predicha por ninguna compañía.",
    colCompany: "Compañía",
    colAssessment: "Evaluación",
    colNotes: "Notas",
    awaitingScansTitle: "Esperando a que se escanee su carta",
    processingTitle: "Analizando carta…",
    processingDescription: "Esto normalmente solo toma un momento.",
    photoTitle: "Foto analizada",
    adjustedChip: "Ajustado",
    originalScorePrefix: "era",
    adjustedBannerTitle: "Ha ajustado esta evaluación",
    adjustedBannerBody:
      "{count} hallazgo(s) detectado(s) automáticamente descartado(s). Cuando la puntuación aún puede deducirse de los hallazgos restantes, se ha actualizado; cuando descartar no dejó nada que medir, se mantiene la medición original. En cualquier caso, el informe se etiquetará claramente como ajustado por el cliente.",
    deleteButton: "Eliminar envío",
    deleteTitle: "¿Eliminar este envío?",
    deleteBody:
      "Esto elimina permanentemente el envío, sus escaneos, el análisis y cualquier informe. No se puede deshacer.",
    deleteConfirm: "Eliminar permanentemente",
    deleteCancel: "Cancelar",
    deleteFailed: "No se pudo eliminar el envío.",
    shareTitle: "Compartir este informe",
    shareBody:
      "Actívelo para obtener un enlace que cualquiera puede abrir, sin cuenta y sin iniciar sesión. Muestra la carta, las puntuaciones y los hallazgos; nunca su correo, su cuenta ni el código del envío.",
    shareUnavailable: "Podrá compartir el informe una vez publicado.",
    shareEnable: "Crear enlace para compartir",
    shareEnabling: "Creando…",
    shareCopy: "Copiar enlace",
    shareCopied: "Copiado",
    shareRotate: "Reemplazar enlace",
    shareRotateBody:
      "El enlace anterior deja de funcionar de inmediato. Quien lo tenga no verá nada.",
    shareDisable: "Dejar de compartir",
    shareDisabledNote: "No se está compartiendo. Nadie puede abrir este informe sin iniciar sesión.",
    shareFailed: "No se pudo cambiar la configuración de compartir.",
  },
  breakout: {
    front: "Frente",
    back: "Reverso",
    zoomedViewLabel: "Vista ampliada",
    okChip: "Correcto",
    flaggedChip: "Marcado",
    noRegionsNote: "No se marcó nada en este lado.",
    showMore: "Mostrar {count} problema(s) más",
    showLess: "Mostrar menos",
    lowConfidenceNote: "El centrado no se pudo medir de forma fiable en esta carta.",
    lowConfidenceGenericNote:
      "Detección de menor confiabilidad: la luz difusa del escaneo solo capta defectos pronunciados. Descártela si no está de acuerdo.",
    dismiss: "Descartar",
    restore: "Restaurar",
    dismissedBadge: "Descartado",
    toggleFailed: "No se pudo actualizar la evaluación.",
    aiObservationsTitle: "Observaciones de IA (asistivas, menor confiabilidad)",
    collapse: "Contraer",
    expand: "Expandir",
    collapseAll: "Contraer todo",
    expandAll: "Expandir todo",
    whyFlagged: "¿Por qué se ha marcado esto? Cómo funciona el análisis",
  },
  inspector: {
    inspect: "Inspeccionar foto",
    close: "Cerrar",
    zoomIn: "Acercar",
    zoomOut: "Alejar",
    resetZoom: "Ajustar",
    hideMarkers: "Ocultar marcas",
    showMarkers: "Mostrar marcas",
  },
  account: {
    title: "Su cuenta",
    subtitle: "Sus datos de acceso y preferencias.",
    emailLabel: "Correo electrónico",
    displayNameLabel: "Nombre para mostrar (opcional)",
    displayNameHint: "Cómo nos dirigimos a usted en correos e informes.",
    marketingLabel: "Quiero recibir novedades ocasionales sobre nuevos servicios",
    marketingHint:
      "Desactivado por defecto. Los avisos sobre sus propios envíos se envían igualmente.",
    save: "Guardar cambios",
    saving: "Guardando…",
    saved: "Cuenta actualizada.",
    saveFailed: "No se pudieron guardar los cambios.",
    unverified: "Su dirección de correo aún no está confirmada.",
    resend: "Reenviar el correo de confirmación",
    resent: "Si esa dirección necesita confirmarse, ya va en camino un enlace nuevo.",
    changePasswordTitle: "Cambiar contraseña",
    currentPassword: "Contraseña actual",
    newPassword: "Contraseña nueva",
    changePassword: "Cambiar contraseña",
    changing: "Cambiando…",
    changed: "Contraseña cambiada. Se ha cerrado la sesión en otros dispositivos.",
    changeFailed: "No se pudo cambiar la contraseña.",
    dangerTitle: "Cerrar su cuenta",
    dangerBody:
      "Esto elimina permanentemente su cuenta, todos los envíos, los escaneos y los informes. No se puede deshacer.",
    deleteButton: "Eliminar mi cuenta",
    deleteConfirmTitle: "¿Eliminar su cuenta?",
    deleteConfirmBody:
      "Todo se elimina de inmediato y de forma permanente. No hay manera de recuperarlo.",
    deleteConfirm: "Eliminar permanentemente",
    deleteCancel: "Cancelar",
    deleteFailed: "No se pudo eliminar su cuenta.",
  },
  forgotPassword: {
    title: "Restablecer su contraseña",
    subtitle:
      "Introduzca su correo y le enviaremos un enlace para establecer una contraseña nueva.",
    email: "Correo electrónico",
    submit: "Enviar enlace",
    submitting: "Enviando…",
    sent: "Si esa dirección tiene una cuenta, ya va en camino un enlace. Revise su bandeja.",
    backToLogin: "Volver a iniciar sesión",
  },
  resetPassword: {
    title: "Elija una contraseña nueva",
    password: "Contraseña nueva",
    passwordHint: "Al menos 8 caracteres.",
    submit: "Establecer contraseña",
    submitting: "Guardando…",
    success: "Su contraseña ha cambiado. Ya puede iniciar sesión.",
    failed: "Este enlace no es válido o ha caducado.",
    requestNew: "Solicitar un enlace nuevo",
    loginLink: "Iniciar sesión",
  },
  upload: {
    title: "Suba las fotos de su carta",
    subtitle: "Añada una foto clara de cada lado, o escanéela con la cámara de su dispositivo.",
    // El contraste con el fondo es lo que permite encontrar los bordes, y es
    // lo unico que el cliente controla de verdad.
    backgroundHint:
      "Coloque la carta sobre una superficie lisa que contraste con ella — una carta oscura sobre fondo claro, una clara sobre fondo oscuro. Ese contraste es lo que permite encontrar los bordes de la carta.",
    frontLabel: "Frente (obligatorio)",
    backLabel: "Reverso (opcional)",
    backHint:
      "Añádalo ahora o más tarde — solo el frente ya le permite obtener una revisión parcial.",
    chooseFile: "Elegir foto",
    uploading: "Subiendo…",
    frontUploadedTitle: "Frente recibido",
    frontUploadedNote:
      "Su revisión parcial está en curso. Añada una foto del reverso en cualquier momento antes de que se apruebe para una revisión completa, o déjelo así.",
    uploadFailed: "Error al subir la imagen",
    invalidImage: "Eso no parece una imagen válida. Pruebe con un JPEG, PNG o TIFF.",
    fileTooLarge: "Esa imagen es demasiado grande.",
  },
  centeringAdjust: {
    toggle: "Ajustar centrado",
    toggleDone: "Listo",
    title: "Revise las líneas de centrado",
    instructions:
      "Estas cuatro líneas marcan dónde se detectó el borde. Si alguna está mal colocada, arrastre su tirador para moverla: las proporciones se actualizan al momento y la puntuación se recalcula al aplicar.",
    disabled: "El ajuste de las líneas de centrado está desactivado.",
    loadFailed: "No se pudo cargar la imagen para ajustarla.",
    leftRight: "Izquierda / derecha",
    topBottom: "Arriba / abajo",
    worstSide: "Lado peor",
    apply: "Aplicar y recalcular",
    applying: "Recalculando…",
    applied: "Centrado recalculado con las líneas que ha fijado.",
    applyFailed: "No se pudo aplicar ese ajuste.",
    reset: "Volver a lo detectado",
    handleLabel: {
      left_px: "Línea del borde izquierdo",
      right_px: "Línea del borde derecho",
      top_px: "Línea del borde superior",
      bottom_px: "Línea del borde inferior",
    },
  },
  cropAdjust: {
    title: "Confirme qué carta analizar",
    instructions: "Arrastre los 4 controles aproximadamente hasta las esquinas de la carta y confirme. No hace falta que sean exactos: los filos de la carta se localizan automáticamente.",
    confirmButton: "Confirmar recorte",
    confirming: "Confirmando…",
    loadFailed: "No se pudo cargar la foto para recortar.",
    confirmFailed: "No se pudo confirmar el recorte.",
    confirmBusy:
      "El analizador está ocupado en este momento. Su recorte no se ha perdido: espere un momento y vuelva a confirmarlo.",
    confirmAlreadyRunning:
      "Ya tiene una carta en análisis. Espere a que termine y luego confirme este recorte.",
    snapButton: "Ajustar a los bordes detectados",
    snapFailed: "No se pudo refinar el recorte.",
    rotateLeft: "Girar a la izquierda",
    rotateRight: "Girar a la derecha",
    checking: "Comprobando el recorte…",
    boundaryWarningTitle: "No se han podido localizar los filos de la carta",
    boundaryWarningHint:
      "Puede enviarla igualmente, pero esta carta volvería sin ninguna puntuación. Ajustar el recorte lo soluciona mucho más a menudo que repetir la foto.",
    adjustInstead: "Prefiero ajustarlo",
    submitAnyway: "Enviar igualmente",
    checkFailed: "No se pudo comprobar el recorte; aún puede confirmarlo.",
  },
  footer: {
    tagline: "Pre-calificación independiente de cartas coleccionables, desde Gibraltar.",
    exploreHeading: "Explorar",
    legalHeading: "Legal",
    connectHeading: "Contacto",
    rights: "Todos los derechos reservados.",
    instagram: "Instagram",
    facebook: "Facebook",
    x: "X",
    whatsapp: "WhatsApp",
    email: "Escríbanos",
  },
  about: {
    title: "Sobre nosotros",
    lede: "Un coleccionista local que quiere que calificar y cuidar sus cartas deje de ser una lotería.",
    body1:
      "{businessName} nació en Gibraltar, y lo lleva alguien que colecciona lo mismo que usted. Quien haya enviado una carta a calificar conoce la sensación: paga la tarifa, envía algo que le importa, espera semanas, y solo entonces descubre si mereció la pena.",
    body2:
      "Ese hueco es lo que este servicio pretende cerrar, y cerrarlo bien acabó exigiendo dos mitades. Una mide la carta y le dice en qué punto está antes de que pague a nadie por calificarla. La otra cuida de la carta en sí: manipulación, conservación, limpieza de superficie y consejo honesto sobre lo que la restauración puede y no puede lograr con seguridad.",
    splitTitle: "Dos caras, un mismo taller",
    splitLede:
      "La misma persona, la misma mesa de trabajo, dos oficios distintos. La mayoría llega buscando uno y acaba necesitando el otro.",
    labTitle: "{businessName}",
    labBody:
      "Saber en qué punto está una carta. Centrado, esquinas, bordes y superficie medidos, con imágenes anotadas que muestran exactamente qué se detectó y por qué. Si una carta no va a calificar como esperaba, mejor saberlo aquí que después de pagar un envío real.",
    careTitle: "{businessName}",
    careBody:
      "Cuidar la carta en sí. Fundas, conservación y manipulación, limpieza cuidadosa de la superficie y una opinión franca sobre si conviene hacer algo o no. Muchas cartas están mejor tal y como están, y se lo diremos.",
    body3:
      "El objetivo más amplio es facilitar el coleccionismo, el cuidado y la calificación de cartas a la gente de Gibraltar y alrededores: un sitio cercano donde preguntar, donde revisen una carta como es debido y, con el tiempo, donde entregarla para calificación sin tener que enviarla usted mismo.",
    honestTitle: "Hablando claro",
    honestBody:
      "Esto es una estimación, no un veredicto. El análisis automático detecta mucho, pero un escaneo plano usa luz difusa en lugar de la luz rasante que emplea una compañía de calificación, así que puede pasar por alto defectos sutiles de superficie y, en ocasiones, marcar la textura de impresión como un defecto. Puede descartar cualquier hallazgo que considere erróneo, y cada informe dice con claridad qué es y qué no es.",
    ctaTitle: "¿Tiene una carta que le genera dudas?",
    ctaBody: "Haga una revisión gratuita y vea el resultado antes de comprometerse a nada.",
  },
  googleAuth: {
    button: "Continuar con Google",
    divider: "o",
    signingIn: "Iniciando sesión…",
    oneMoment: "Un momento mientras terminamos de iniciar su sesión.",
    problemTitle: "No se completó el inicio de sesión",
    missingToken: "Ese enlace no traía una sesión. Inténtelo de nuevo.",
    failed: "No pudimos completar el inicio de sesión. Inténtelo de nuevo.",
    backToLogin: "Volver a iniciar sesión",
    errorPrefix: "Inicio de sesión con Google:",
  },
  quota: {
    chipRemaining: "{n} análisis restantes",
    chipExhausted: "Sin análisis disponibles",
    chipExhaustedIn: "Se renueva en {time}",
    ariaLabel: "Análisis restantes en este periodo",
    unitDay: "d",
    unitHour: "h",
    unitMinute: "min",
    exhaustedTitle: "Ha agotado los análisis de este periodo",
    exhaustedBody:
      "Su cuota se renueva automáticamente en {time}. Una suscripción elimina el límite por completo.",
    exhaustedBodyNoTimer:
      "Su cuota se renueva automáticamente. Una suscripción elimina el límite por completo.",
    seePlans: "Ver planes",
  },
  care: {
    title: "Cuidar la carta que ya tiene.",
    lede: "Limpieza, protección y consejo honesto sobre restauración, con los riesgos expuestos con claridad antes de tocar nada.",
    intro:
      "{businessName} es la parte del servicio dedicada al cuidado. Mientras que el lado de análisis le dice si merece la pena enviar una carta a calificar, este lado se ocupa del objeto físico: cómo se guarda, cómo se manipula, y qué se puede y no se puede mejorar con seguridad.",
    ctaPrimary: "Consultar sobre una carta",
    ctaSecondary: "Volver al análisis de calificación",
    s1Title: "Manipulación y almacenamiento",
    s1Body:
      "La mayor parte del daño evitable ocurre entre que la carta sale del sobre y llega a una funda. El consejo aquí es gratuito y específico para lo que usted tiene, no una lista genérica.",
    s2Title: "Limpieza de superficie",
    s2Body:
      "La suciedad superficial y las huellas suelen poder tratarse con seguridad. Todo lo que alteraría la superficie impresa en sí no es limpieza, y se trata como restauración más abajo.",
    s3Title: "Consulta de restauración",
    s3Body:
      "Algunos problemas pueden mejorarse; muchos no, y algunos intentos empeoran las cosas. La consulta es gratuita precisamente para que nadie pague por escuchar un no.",
    servicesTitle: "Servicios de cuidado de cartas",
    servicesLede:
      "Todo lo que implica manipular físicamente una carta suya: almacenamiento, limpieza, restauración y hacerla llegar con seguridad a una compañía de calificación.",
    warningTitle: "Lea esto antes de pedir una restauración",
    warningBody:
      "La restauración conlleva un riesgo real. Una carta restaurada puede ser calificada como alterada, o rechazada sin más, por una compañía de calificación, y ese resultado es permanente. No se intenta nada sin hablarlo antes con usted y acordarlo por escrito. Si la respuesta honesta es dejar la carta en paz, esa será la respuesta que reciba.",
  },
  pricing: {
    title: "Precios",
    subtitle:
      "Dos servicios en el lanzamiento: análisis a partir de sus propias fotos y una revisión de la carta en mano. Abajo está lo que cuesta cada uno, sin nada oculto hasta el pago.",
    softwareHeading: "Análisis de imagen",
    softwareLede:
      "Suba fotos de una carta y reciba un informe de pre-clasificación: centrado, esquinas, filos y superficie, con los factores de riesgo señalados.",
    planFree: "Gratis",
    planPack: "Bono de créditos",
    planMonthly: "Mensual",
    planAnnual: "Anual",
    planFreeNote: "El informe gratuito no está recortado: recibe el mismo análisis que cualquier plan de pago.",
    planPackNote: "Se paga una vez y se usa a lo largo del año. Para quien prefiere no suscribirse.",
    planMonthlyNote: "Para uso habitual, se cancela cuando quiera.",
    planAnnualNote: "Lo mismo que el mensual, pagado de una vez.",
    perMonth: "al mes",
    perYear: "al año",
    oneOff: "pago único",
    checksPerPeriod: "{count} análisis cada {days} días",
    checksUnlimited: "Análisis ilimitados",
    checksOneOff: "{count} análisis",
    freeAllowance: "Las cuentas gratuitas incluyen {allowance}.",
    freeCta: "Empezar un análisis gratis",
    paidCta: "Contactar",
    paidNote: "Por ahora los planes de pago se gestionan directamente: envíe un mensaje y se configura a mano.",

    physicalHeading: "Pre-clasificación personalizada",
    physicalLede:
      "La carta revisada en mano: escaneada, medida, comentada por escrito y con una opinión honesta sobre si merece la pena enviarla.",
    physicalQty: "Cartas",
    physicalPer: "Por carta",
    physicalTurnaround: "5-7 días laborables desde la recepción.",
    physicalLocation: "Solo Gibraltar en el lanzamiento, para mantener la logística sencilla.",
    physicalPostage: "Envío de vuelta a precio de coste, con seguimiento y asegurado.",
    physicalCta: "Solicitar una revisión",

    bundlesHeading: "Paquetes",
    triageName: "Revisión de colección",
    triageBody:
      "Traiga un archivador o una caja. Se revisa todo, lo mejor recibe una pre-clasificación física y usted recibe un veredicto por escrito: estas a clasificar, estas a vender sin clasificar, estas no compensan ni el envío.",
    triageGuide: "Precio orientativo de unos {price}: los trabajos varían demasiado para cotizar a ciegas.",
    triageCta: "Preguntar por una colección",
    doubleName: "Doble revisión",
    doubleBody:
      "Reserve un lote de 10 cartas o más y se incluyen tres meses del plan de pago.",

    extrasHeading: "Mientras esté suscrito",
    discount: "{percent}% de descuento en cualquier servicio físico mientras dure su suscripción.",
    founder: "Precio fundador: los primeros {seats} suscriptores anuales pagan {price}, bloqueado mientras sigan suscritos.",

    disclaimer:
      "No se garantiza ninguna nota. El informe es una evaluación de factores de riesgo, no una predicción que vincule a {companies}.",
  },
  services: {
    title: "Servicios",
    subtitle:
      "Empiece con una revisión gratuita. Todo lo demás está en desarrollo: escríbanos si necesita algo de esta lista antes de que esté disponible.",
    statusAvailable: "Disponible ya",
    statusComingSoon: "Próximamente",
    statusPlanned: "Previsto",
    includesLabel: "Incluye",
    contactCta: "Contactar",
    startCta: "Empezar revisión gratuita",
    methodologyCta: "Cómo funciona el análisis",
    pricingNote:
      "Los precios de los servicios de pago aún no están fijados. Nada de esta página le compromete a nada, y no se trabaja sobre ninguna carta sin acordar antes el coste con usted.",
    tier1Name: "Análisis de imagen e informe",
    tier1Body:
      "El servicio que ya funciona hoy, gratuito y con un límite de cartas revisadas. Suba una foto o envíenos la carta, y reciba un desglose completo.",
    tier1Point1: "Análisis medido de centrado, esquinas, bordes y superficie",
    tier1Point2: "Imágenes anotadas que muestran exactamente qué se marcó y dónde",
    tier1Point3:
      "Notas comparativas sobre cómo suelen tratar esos hallazgos {companies}",
    tier1Point4: "Un informe PDF descargable que puede conservar",
    tier2Name: "Suscripción ilimitada",
    tier2Body:
      "Para quien va a revisar una colección entera y no una carta suelta. Todo lo del plan gratuito sin el límite, y a un precio deliberadamente bajo.",
    tier2Point1: "Revisiones e informes ilimitados",
    tier2Point2: "Procesamiento prioritario",
    tier2Point3:
      "Segunda opinión asistida por IA sobre superficie y dobleces, cuando esté lista",
    tier3Name: "Pre-calificación personalizada",
    tier3Body:
      "Una carta inspeccionada a mano y no solo por software, para cuando el análisis automático no basta: una carta de alto valor, o una que está justo en el límite entre dos calificaciones.",
    tier3Point1: "Todo lo del informe estándar, más una inspección física",
    tier3Point2:
      "Notas escritas sobre los puntos concretos que un calificador probablemente discutirá",
    tier3Point3: "Una opinión franca sobre si merece la pena enviar la carta",
    crossToCareTitle: "¿Ya tiene la carta? {businessName} la cuida",
    crossToCareBody:
      "El análisis le dice si merece la pena enviar una carta a calificar. {businessName} es la otra mitad: consejo sobre almacenamiento y manipulación, limpieza de superficie, consultas honestas de restauración y embalaje adecuado para el trayecto.",
    crossToLabTitle: "¿Aún no sabe si merece calificarla? Empiece por {businessName}",
    crossToLabBody:
      "Antes de pagar por calificar una carta, {businessName} mide el centrado, las esquinas, los bordes y la superficie, y le indica cómo es probable que la traten las principales compañías, para que lo sepa antes de pagar y no después.",
    crossCta: "Ver servicios de {businessName}",
    tier4Name: "Restauraciones",
    tier4Body:
      "Algunos problemas se pueden mejorar; muchos no, y algunos intentos empeoran las cosas. La consulta es gratuita precisamente para que nadie pague por que le digan que no.",
    tier4Point1: "Consulta gratuita antes de acordar o intentar nada",
    tier4Point2: "Una valoración honesta de lo que se puede mejorar de forma realista",
    tier4Point3: "Los riesgos por escrito, incluido el riesgo de dañar la carta",
    tier4Warning:
      "La restauración conlleva un riesgo real, y una carta restaurada puede ser calificada como alterada o rechazada por una compañía de calificación. No se intenta nada sin comentarlo antes con usted y acordarlo por escrito.",
    tier5Name: "Preparación para calificación",
    tier5Body:
      "Cartas preparadas y embaladas correctamente para su envío a una compañía de calificación, para que no sufran daños en tránsito que no tenían al salir de sus manos.",
    tier5Point1: "Fundas, card savers y embalaje protector adecuados",
    tier5Point2: "Documentación de envío preparada y revisada",
    tier5Point3: "Tarifa por carta con descuentos por volumen",
    tier6Name: "Punto de recogida y envío",
    tier6Body:
      "Un punto de entrega local en Gibraltar para cartas destinadas a las compañías de calificación, para que no tenga que gestionar usted el envío internacional y el seguro de una sola carta.",
    tier6Point1: "Entrega local en lugar de envío al extranjero",
    tier6Point2: "Cartas agrupadas en envíos por volumen para reducir el coste por carta",
    tier6Point3: "Seguimiento desde la entrega hasta la devolución",
  },
  howItWorks: {
    title: "Cómo funciona",
    subtitle: "De la carta al informe en cuatro pasos.",
    step1Title: "Cree un envío",
    step1Body:
      "Díganos el juego y la carta. Es cuestión de un momento, y le asigna a su carta un código de referencia que puede seguir.",
    step2Title: "Añada una foto, o envíe la carta",
    step2Body:
      "Suba una foto nítida y plana del frente (y del reverso si lo tiene), o envíenos la carta y la escanearemos como es debido. Usted confirma un recorte aproximado para que sepamos a qué carta de la foto se refiere; los filos exactos se localizan después de forma automática, así que el recorte no tiene que ser perfecto.",
    step3Title: "Se ejecuta el análisis",
    step3Body:
      "El centrado se mide a partir del ancho de los márgenes, se revisan esquinas y bordes en busca de blanqueo y desgaste, y se examina la superficie buscando arañazos y dobleces. Normalmente tarda unos instantes.",
    step4Title: "Lea su informe",
    step4Body:
      "Recibe una puntuación por categoría, imágenes anotadas que señalan cada hallazgo, y notas sobre cómo suelen tratarlos las principales compañías. Puede descartar lo que considere erróneo, y el informe indicará con claridad que fue ajustado.",
    faqTitle: "Preguntas frecuentes",
    faq1Q: "¿Es una calificación oficial?",
    faq1A:
      "No. Es una estimación independiente para ayudarle a decidir si enviar la carta. No estamos afiliados a PSA, BGS, CGC, TAG, ACE ni a ninguna otra compañía, y nunca predecimos una calificación numérica en su nombre.",
    faq2Q: "¿Qué precisión tiene?",
    faq2A:
      "El centrado se mide y es el más fiable de los cuatro. Esquinas y bordes funcionan bien. La superficie es el punto débil: un escaneo plano usa luz difusa, mientras que una compañía de calificación usa luz rasante que proyecta sombras en los arañazos, así que pueden pasarse por alto defectos leves y a veces se marca la textura de impresión.",
    faq3Q: "¿Por qué marcó algo que no existe?",
    faq3A:
      "Normalmente texto o textura de impresión leídos como un arañazo. Puede descartar cualquier hallazgo con el que no esté de acuerdo. Cuando los hallazgos restantes aún sostienen una puntuación, esta se actualiza al instante; cuando descartar no deja nada que medir, se mantiene la medición original en lugar de saltar a una puntuación perfecta. El informe pasa entonces a indicar claramente que usted lo ajustó.",
    faq4Q: "¿Y si la foto no es perfecta?",
    faq4A:
      "Fotografíe la carta plana, de frente, ocupando casi todo el encuadre, con luz uniforme y sin reflejos. Podrá ajustar el recorte antes de que se ejecute el análisis, y hay un ayudante de ajuste a los bordes detectados si las esquinas no quedan exactas.",
    faq5Q: "¿Qué pasa con mi carta si la envío?",
    faq5A:
      "Se escanea y se devuelve. La manipulación se reduce al mínimo, y no se hace nada a una carta física más allá de escanearla salvo que usted lo haya pedido y se haya acordado por escrito.",
    faq6Q: "¿Qué pasa con mis imágenes?",
    faq6A:
      "Se almacenan para que su informe siga funcionando, y no se usan para nada más. Puede eliminar un envío en cualquier momento, lo que borra sus escaneos, el análisis y el informe.",
    ctaTitle: "¿Listo para probarlo?",
    ctaBody: "Probarlo es gratuito.",
    methodologyLink: "Leer la metodología completa",
  },
  methodology: {
    title: "Cómo funciona el análisis",
    subtitle:
      "Qué mide el software, cómo decide y en qué se equivoca. Todas las imágenes de esta página son resultados reales del mismo código que lee su carta.",

    demoTitle: "Sobre la carta de estas imágenes",
    demoBody:
      "La carta que aparece abajo no es real. Se creó para esta página y se pasó por el análisis de verdad, así que lo que ve son detecciones auténticas, no un diagrama de lo que nos gustaría que hiciera. Usamos una carta inventada porque la ilustración de una carta real pertenece a su editorial, y el escaneo de un cliente pertenece al cliente.",

    prepTitle: "Antes de medir nada",
    prepBody:
      "Se localiza la carta en la foto, se endereza y se recorta a sus propios bordes. Se ajusta una recta a cada uno de los cuatro lados, usando los tramos rectos e ignorando las esquinas, y los cuatro vértices salen de donde se cruzan esas rectas: así, una esquina a la que le falta material sigue teniendo una punta ideal conocida contra la que medir esa pérdida. Las rectas se sitúan con precisión de fracciones de píxel, lo cual importa porque un píxel entero ya es una parte apreciable del desgaste que se mide. El recorte que usted confirma nos dice dónde mirar, pero no decide dónde están los filos de la carta; eso lo decide la carta. La escala sale del tamaño físico real de la carta, no del archivo de imagen. Los PPP guardados en la foto de un móvil no tienen nada que ver con cuántos píxeles cubren la carta, así que partimos de que una carta estándar mide 63mm por 88mm. Por eso el informe le da milímetros que puede comprobar con una regla.",

    centeringTitle: "Centrado",
    centeringMeasures: "Qué mide",
    centeringMeasuresBody:
      "El ancho del borde impreso en los cuatro lados, y cuán desigual fue el corte de la carta.",
    centeringHow: "Cómo",
    centeringHowBody:
      "Se muestrea el color del propio borde impreso justo por dentro de cada filo y luego se busca hacia dentro dónde deja de coincidir con él: ese es el canto interior del borde. Hacerlo en cada posición a lo largo de un lado, y no en unas pocas líneas, da una recta que puede ajustarse en lugar de un único número. De ese ajuste salen dos cosas. Los anchos del borde dan la habitual proporción izquierda/derecha y superior/inferior. La *pendiente* da algo que un solo número por lado no puede dar: si el borde corre paralelo al corte o se ensancha de forma constante a lo largo de él. Una carta puede estar impresa recta y cortada torcida, y entonces promedia una proporción perfecta aunque se vea visiblemente sesgada; los calificadores lo penalizan aparte, y nosotros también.",
    centeringWrong: "En qué se equivoca",
    centeringWrongBody:
      "Una carta a sangre no tiene un borde limpio que encontrar, y el software lo dice en vez de adivinar: si muy pocas posiciones a lo largo de un lado dan con un borde, o lo que dan no es recto, el centrado se informa como no medible en lugar de recibir un número de aspecto plausible. Una carta holográfica es el caso intermedio incómodo: el patrón dispersa las lecturas individuales, así que el ancho del borde se sigue midiendo sobre el lado en conjunto pero la comprobación de corte torcido no está disponible, y el informe indica cuál de las dos le ha tocado. El fallo más difícil es el más silencioso: un borde localizado con confianza en el sitio equivocado, normalmente donde la textura de impresión o un reflejo cruzan el salto de color antes que el borde real. Por eso las líneas se muestran sobre su carta y se pueden mover: si una está visiblemente mal, arrastrarla hasta el borde real es más rápido que cualquier cantidad de fotos nuevas.",
    centeringAlt:
      "La carta de demostración con el borde impreso resaltado y los cuatro anchos de borde etiquetados en milímetros.",
    centeringCaption:
      "Las cuatro medidas y la proporción que producen. Esta carta se cortó claramente hacia un lado.",

    cornersTitle: "Esquinas",
    cornersMeasures: "Qué mide",
    cornersMeasuresBody:
      "Cuánto cartón falta en cada una de las cuatro esquinas, en milímetros cuadrados, y cuánto se ha deshilachado cada una hacia el cartón blanco de debajo.",
    cornersHow: "Cómo",
    cornersHowBody:
      "Dos medidas distintas. Para la forma: los cuatro vértices se obtienen prolongando los filos ajustados de la carta hasta que se cruzan, lo que da la punta que habría tenido una esquina perfecta, y todo lo que falte dentro de esa esquina ideal se mide como superficie. Una carta se troquela con un redondeo de aproximadamente 1,5mm, así que esa parte se espera y se perdona; lo que sobra es desgaste. Para el color: la punta se compara con el mismo borde un poco más allá del filo, en un espacio de color que separa cuán clara es una zona de cuán colorida es, porque una esquina deshilachada se vuelve a la vez más clara y menos colorida. La peor de las dos lecturas fija la puntuación de la esquina, en lugar de sumarse: una esquina astillada casi siempre está también blanqueada, y no se debe penalizar dos veces un mismo daño. La peor esquina de la carta pesa después la mitad de toda la categoría.",
    cornersWrong: "En qué se equivoca",
    cornersWrongBody:
      "La medida de superficie tiene un límite de resolución. El contorno de la carta se determina con precisión de píxeles enteros, lo que en una foto típica supone alrededor de un cuarto de milímetro cuadrado de incertidumbre, así que el desgaste más fino que una muesca de medio milímetro no se informa en absoluto: preferimos no verlo a inventarlo. El margen de 1,5mm del troquelado es una cifra estándar y no una medida de su carta concreta, así que una carta cortada con un radio más ajustado o más amplio parecerá algo desgastada o algo generosa. La parte del color sigue teniendo dificultades con un borde blanco o muy pálido, donde hay poco color que perder; la parte de la superficie no depende del color del borde, y por eso esas cartas ya no son el punto ciego que eran. Ninguno de los umbrales procede de una norma de calificación publicada.",
    cornersAlt:
      "La esquina superior izquierda ampliada de la carta de demostración, con la zona de la punta y la de referencia resaltadas y el cambio medido de luminosidad y color.",
    cornersCaption:
      "La punta frente a su referencia. Más clara y menos colorida significa que la esquina se ha desgastado hacia el cartón; la superficie que falta se mide aparte, contra el vértice que la carta habría tenido.",

    edgesTitle: "Bordes",
    edgesMeasures: "Qué mide",
    edgesMeasuresBody:
      "Dos cosas: el blanqueamiento a lo largo de cada filo y cuán recto es realmente el corte, medido en milímetros.",
    edgesHow: "Cómo",
    edgesHowBody:
      "Para el blanqueamiento: primero se localiza el borde impreso, mirando hacia dentro desde el filo hasta que cambia el color, y solo se usa como referencia cartón de dentro de ese borde. Esto importa más de lo que parece: antes la referencia estaba a una profundidad fija y, en una carta con el borde más estrecho que esa profundidad, caía sobre la ilustración. La comparación medía entonces la diferencia entre el borde y el arte que enmarca, que es un rasgo de diseño y no desgaste. Un tramo largo e ininterrumpido pesa más que la misma cantidad repartida, porque así es como se juzga en realidad. Para la forma: se ajusta una recta a cada corte y se registra cuánto se aparta de ella el filo real, de modo que una muesca se mide como una profundidad física en milímetros en lugar de deducirse del color. La peor de las dos lecturas fija la puntuación del filo, no su suma: un filo deshilachado suele presentar ambas cosas y no debe penalizarse dos veces por un mismo daño.",
    edgesWrong: "En qué se equivoca",
    edgesWrongBody:
      "Si el borde mide menos de milímetro y medio aproximadamente, no hay cartón limpio con el que comparar junto al filo, y ese lado se juzga solo por la forma; el informe lo indica cuando ocurre en lugar de adivinar. La medida de forma describe el corte, así que no puede ver un desgaste que haya decolorado la carta sin deformarla, y la medida de color no puede ver un filo biselado o mordido que conservó su color; cada una cubre el punto ciego de la otra, y por eso se toman ambas. La textura foil u holográfica cerca de un filo aún puede registrarse en cualquiera de las dos.",
    edgesAlt:
      "El borde derecho ampliado de la carta de demostración, con un tramo blanco desgastado dentro de la franja muestreada, junto a la franja de referencia tomada de dentro del borde impreso.",
    edgesCaption:
      "La franja muestreada y su referencia, tomada de dentro del borde localizado en vez de a una profundidad fija.",

    surfaceTitle: "Superficie",
    surfaceMeasures: "Qué mide",
    surfaceMeasuresBody: "Arañazos, líneas de impresión y otras marcas en la cara de la carta.",
    surfaceHow: "Cómo",
    surfaceHowBody:
      "El software desplaza una ventana pequeña por la carta y mide cuánto cambia la imagen dentro de ella. Una zona lisa y limpia apenas cambia; un arañazo cambia bruscamente. Todo lo que quede muy por encima de la media de la propia carta se marca, y después se mide cada zona marcada: un arañazo real es largo y su trazo es fino, de unas seis décimas de milímetro. El texto impreso tiene aproximadamente el doble de grosor, y esa diferencia es lo que permite distinguirlos.",
    surfaceWrong: "En qué se equivoca",
    surfaceWrongBody:
      "Es la más débil de las cuatro, y preferimos decirlo a que lo descubra usted. Un escáner plano ilumina la carta de forma uniforme; un calificador profesional usa una luz casi rasante que proyecta una sombra a lo largo del arañazo y lo hace evidente. Nosotros no tenemos esa sombra, así que los arañazos leves pueden pasar desapercibidos, y detalles impresos pueden marcarse sin motivo.",
    surfaceRawAlt:
      "La carta de demostración con todo lo que detectó el análisis resaltado en rojo: todas las líneas de texto y el arañazo.",
    surfaceRawCaption:
      "Todo lo que ve la primera pasada. El texto impreso está incluido: para un detector de contraste, una letra se parece bastante a un arañazo.",
    surfaceFilteredAlt:
      "La misma carta tras el filtrado, con recuadros sobre el arañazo, el borde superior del panel de ilustración y dos palabras del texto.",
    surfaceFilteredCaption:
      "Lo que supera el filtro. El arañazo se conserva, pero también el borde superior del panel de ilustración y dos palabras de texto. Esos dos últimos son falsos positivos, y por eso puede eliminar cualquier detección con la que no esté de acuerdo.",

    creasesTitle: "Dobleces",
    creasesMeasures: "Qué mide",
    creasesMeasuresBody:
      "Líneas largas que cruzan la carta ignorando el diseño impreso.",
    creasesHow: "Cómo",
    creasesHowBody:
      "Se realza mucho el contraste y solo se conservan las líneas largas y bastante rectas del interior de la carta; el borde se omite, porque los cantos del marco impreso también son líneas rectas y largas. Las líneas casi idénticas se fusionan para no informar tres veces del mismo doblez.",
    creasesWrong: "En qué se equivoca",
    creasesWrongBody:
      "Un doblez necesita luz en ángulo que proyecte sombra sobre el relieve, y un escaneo plano no la da. Por eso esta detección es deliberadamente informativa: un doblez detectado se le muestra, pero no modifica ninguna puntuación. Las cartas foil y holográficas generan falsos positivos con facilidad.",
    creasesAlt:
      "La carta de demostración con dos líneas detectadas: el doblez y el borde superior del panel de ilustración.",
    creasesCaption:
      "Dos líneas encontradas: el doblez y el borde superior del panel de ilustración, que está impreso y no es un daño. Justo por eso los dobleces no alteran la puntuación.",

    confidenceTitle: "Cuánto fiarse de cada número",
    confidenceBody:
      "No son igual de fiables, y tratarlos como si lo fueran sería engañoso.",
    confidence1:
      "El centrado se mide, no se estima. Fíese de él, salvo que aparezca marcado como de menor confianza.",
    confidence2:
      "Esquinas y bordes van bien. Comparan elementos equivalentes de la misma carta.",
    confidence3:
      "La superficie es la más débil, por el motivo de iluminación explicado arriba. Lea las detecciones, mire las imágenes y use sus propios ojos.",
    confidence4: "Los dobleces son solo informativos y nunca afectan a una puntuación.",

    adjustTitle: "Cuando se equivoca, decide usted",
    adjustBody:
      "Hay dos cosas que puede corregir, y funcionan de forma distinta. Cualquier hallazgo puede descartarse: si los que quedan siguen sosteniendo una puntuación, se recalcula al momento, y si descartar no deja nada desde donde medir, la medición original se mantiene y su desacuerdo queda registrado junto a ella. Descartar algo dice que nos equivocamos, lo cual no es prueba de que la carta esté impecable, y sería deshonesto conceder una puntuación perfecta por eso. El centrado además le deja mover las propias líneas del borde. Si el software colocó una donde no iba, puede arrastrarla hasta el borde real y la puntuación se recalcula desde donde usted la puso: es una corrección, no una objeción, y por eso sí produce un número nuevo. El movimiento está limitado a unos milímetros respecto a donde se detectó el borde, de modo que una línea se puede corregir pero no inventar, y devolver todas las líneas a su sitio original elimina el ajuste por completo. En cualquier caso el informe indica con claridad, en todas sus páginas, que usted lo ajustó y qué cambió. Esa marca no se puede desactivar: un informe ajustado que pareciera idéntico a uno sin ajustar no valdría nada para quien se lo enseñe.",

    notTitle: "Lo que esto no es",
    notBody:
      "Es una estimación independiente para ayudarle a decidir si merece la pena enviar una carta. No es una calificación, y nunca predice una nota en nombre de ninguna empresa calificadora. No estamos afiliados a {companies} ni a ninguna otra empresa de calificación. Sus normas son suyas, cambian, y el criterio de un calificador humano en un día concreto no es algo que un software pueda prometer reproducir.",

    ctaTitle: "Véalo en su propia carta",
    ctaBody: "Probarlo es gratuito y puede descartar lo que no le convenza.",
  },
  publicReport: {
    metaDescription:
      "Una estimación independiente de pre-calificación: centrado, esquinas, bordes y superficie, medidos a partir de fotografías.",
    whatThisIsTitle: "Qué es esto",
    whatThisIsBody:
      "Una estimación independiente del estado de una carta, medida a partir de fotografías mediante análisis de imagen automatizado. No es una calificación ni predice ninguna.",
    notAffiliated:
      "No somos una compañía de calificación y no estamos afiliados a {companies} ni a ninguna otra compañía de calificación.",
    checkedOn: "Revisada el",
    scoresTitle: "Lo que encontró el análisis",
    surfaceCaveat:
      "La superficie es la menos fiable de las cuatro. Estas fotografías están iluminadas de forma uniforme y no en ángulo, así que pueden pasarse por alto rayones finos y a veces se marca la textura de impresión como uno.",
    adjustedTitle: "Ajustado por el propietario de la carta",
    adjustedBody:
      "Quien realizó esta revisión descartó {count} hallazgo(s) detectado(s) automáticamente, y las puntuaciones reflejan eso en lugar del análisis sin alterar.",
    methodologyLink: "Cómo funciona el análisis",
    ctaTitle: "Revise su propia carta",
    ctaBody: "Suba una foto y reciba el mismo desglose. Probarlo es gratuito.",
    ctaButton: "Empezar un análisis gratis",
    notFoundTitle: "Este enlace no está disponible",
    notFoundBody:
      "Puede que quien lo compartió lo haya desactivado, lo haya reemplazado por uno nuevo, o que nunca haya existido. Pídale un enlace actualizado.",
  },
  contact: {
    title: "Contacto",
    subtitle:
      "Dudas sobre una carta, una restauración o cualquier cosa de la página de servicios: pregunte sin problema.",
    emailLabel: "Correo electrónico",
    locationLabel: "Dónde estamos",
    whatsappLabel: "WhatsApp",
    whatsappCta: "Escríbanos por WhatsApp",
    responseLabel: "Tiempo de respuesta",
    responseBody: "Normalmente respondemos en {days} día(s) laborable(s).",
    inPersonLabel: "En persona",
    inPersonBody:
      "Estamos en Gibraltar y podemos acordar una entrega en mano en lugar de enviar la carta por correo. Escríbanos y concretamos hora y lugar.",
    consultationTitle: "Las consultas de restauración son gratuitas",
    consultationBody:
      "Si duda si algo se puede mejorar, pregunte antes de intentar nada por su cuenta. No cobramos por decirle que lo mejor es no tocar una carta.",
    noneTitle: "Datos de contacto próximamente",
    noneBody: "Aún no se han publicado los datos de contacto. Vuelva a consultarlo en breve.",
    formTitle: "Envíe un mensaje",
    formLede:
      "¿Prefiere un formulario? Rellénelo y nos llegará directamente. Puede preguntar por cualquiera de las dos partes del servicio.",
    nameLabel: "Su nombre",
    namePlaceholder: "¿Cómo le llamamos?",
    emailPlaceholder: "usted@ejemplo.com",
    emailHelp: "Para poder responderle. No se usa para nada más.",
    topicLabel: "¿Sobre qué es?",
    topicLab: "{businessName}: análisis de calificación",
    topicCare: "{businessName}: cuidado de cartas",
    topicOther: "Otra cosa",
    subjectLabel: "Asunto",
    subjectPlaceholder: "Unas palabras sobre lo que necesita",
    codeLabel: "Código de envío",
    codeOptional: "opcional",
    codePlaceholder: "SUB-00001",
    codeHelp: "Si su pregunta es sobre una carta que ya nos ha enviado.",
    messageLabel: "Su mensaje",
    messagePlaceholder: "Cuéntenos sobre la carta, o pregunte lo que quiera.",
    submit: "Enviar mensaje",
    sending: "Enviando...",
    successTitle: "Mensaje enviado",
    successBody:
      "Gracias, lo hemos recibido y le responderemos a la dirección que nos ha dado. Si es urgente, WhatsApp suele ser más rápido.",
    successAgain: "Enviar otro",
    errorGeneric:
      "Algo ha fallado al enviarlo. Inténtelo de nuevo o escríbanos directamente por correo.",
    errorRequired: "Rellene este campo.",
    errorEmail: "Eso no parece una dirección de correo.",
    errorMessageShort: "Escriba un poco más para que podamos ayudarle de verdad.",
  },
  terms: {
    title: "Términos y condiciones",
    updated: "Última actualización",
    updatedValue: "Agosto de 2026",
    intro:
      "Estos términos regulan su uso de {businessName}. Al crear una cuenta o enviar una carta, los acepta. Lea en particular el aviso siguiente.",
    disclaimerTitle: "Aviso importante",
    disclaimerBody:
      "{businessName} es una estimación independiente. No está afiliada, respaldada ni garantiza el resultado de PSA, Beckett Grading Services (BGS), CGC, TAG, ACE ni ninguna otra compañía de calificación externa. Nada de lo que producimos es una calificación, una predicción de calificación ni una promesa sobre lo que decidirá ninguna compañía. Una carta con buena puntuación aquí puede calificar por debajo de lo esperado, y al revés.",
    s1Title: "1. Qué hace este servicio",
    s1Body:
      "Analizamos imágenes de sus cartas coleccionables y elaboramos un informe sobre centrado, esquinas, bordes y superficie, junto con notas sobre los puntos de discrepancia que podrían afectar al trato de la carta en distintas compañías. El informe es informativo y busca ayudarle a decidir si pagar un envío real de calificación.",
    s2Title: "2. Qué no hace este servicio",
    s2Body:
      "No calificamos cartas, no emitimos calificaciones ni actuamos en nombre de ninguna compañía de calificación. No garantizamos que una carta reciba una calificación concreta, que sea aceptada para calificación ni que aumente de valor. No somos un servicio de tasación y nuestros informes no son una valoración.",
    s3Title: "3. Precisión y limitaciones conocidas",
    s3Body:
      "El análisis automático de imagen tiene límites reales y preferimos declararlos a ocultarlos. Los escaneos usan luz difusa en lugar de la luz rasante de una compañía de calificación, por lo que pueden pasarse por alto arañazos y dobleces leves. El texto impreso y los patrones holográficos pueden marcarse ocasionalmente como defectos. La precisión de las medidas depende de la calidad y el encuadre de la imagen que aporte. Los hallazgos marcados como de menor confiabilidad son exactamente eso. Trate el informe como un dato más, no como una decisión en sí misma.",
    s4Title: "4. Informes ajustados por usted",
    s4Body:
      "Puede descartar hallazgos concretos que considere incorrectos. Cuando los hallazgos restantes aún sostienen una puntuación, esta se actualiza en consecuencia; cuando descartar no deja nada que medir, se mantiene la medición original. Todo informe en el que lo haya hecho queda etiquetado como ajustado por el cliente, y se muestran tanto la puntuación original como la ajustada. Usted es responsable de los ajustes que realice, y un informe ajustado no debe presentarse a terceros como una evaluación sin modificar.",
    s5Title: "5. Su cuenta",
    s5Body:
      "Los envíos, escaneos, análisis e informes se conservan mientras su cuenta esté abierta, para que pueda volver a consultarlos. Eliminar un envío borra sus escaneos, su análisis y su informe del servicio de inmediato. Las copias de seguridad son la única excepción, y preferimos decirlo a dar a entender lo contrario: se guardan cifradas durante un máximo de 30 días y después se eliminan, así que un envío eliminado puede permanecer en una copia de seguridad durante ese tiempo. Si alguna vez restauramos a partir de una, volvemos a aplicar las eliminaciones hechas desde que se tomó. Si nos pide cerrar su cuenta, eliminaremos sus datos personales en las mismas condiciones, conservando solo lo que estemos legalmente obligados a retener.",
    s6Title: "6. Cartas físicas",
    s6Body:
      "Cuando nos envíe una carta, la tratamos con cuidado y reducimos la manipulación al mínimo. No se hace nada a una carta física más allá de escanearla salvo que usted lo haya solicitado expresamente y lo hayamos acordado por escrito. El envío hasta nosotros y el seguro en tránsito por el valor que considere adecuado corren de su cuenta. Los trabajos de restauración, cuando se acuerden, conllevan un riesgo inherente de daño y una carta restaurada puede ser calificada como alterada o rechazada por una compañía de calificación; ese riesgo se explica y se acuerda antes de comenzar cualquier trabajo.",
    s7Title: "7. Tarifas",
    s7Body:
      "El análisis básico de imagen es actualmente gratuito, sujeto a límites de uso razonable. Los servicios de pago se describen en la página de Servicios; cuando un servicio figura como próximamente o previsto, todavía no está disponible para su contratación. Las tarifas de cualquier servicio de pago se acuerdan con usted antes de iniciar el trabajo. Nada se compra a través de este sitio web: cuando contrata un servicio, acordamos el pago con usted directamente. La cancelación y los reembolsos se rigen por la Política de reembolsos, que forma parte de estos términos.",
    s8Title: "8. Limitación de responsabilidad",
    s8Body:
      "En la medida en que lo permita la ley, no respondemos de las decisiones que tome a partir de un informe, de los resultados de calificación, del lucro cesante o el valor esperado, ni de la diferencia entre un informe y la decisión de una compañía de calificación. Nada en estos términos limita la responsabilidad por muerte o daños personales causados por negligencia, por fraude, ni por cualquier otro supuesto que no pueda limitarse legalmente. Cuando una carta se pierda o dañe bajo nuestra custodia, nuestra responsabilidad se limita a las condiciones de manipulación acordadas para esa carta.",
    s9Title: "9. Cambios",
    s9Body:
      "Podemos actualizar estos términos a medida que evolucione el servicio. La fecha al inicio de esta página indica cuándo cambiaron por última vez, y seguir usando el servicio tras un cambio implica que acepta los términos actualizados.",
    s10Title: "10. Legislación aplicable",
    s10Body:
      "Estos términos se rigen por la legislación de Gibraltar, y las controversias corresponden a los tribunales de Gibraltar.",
    s11Title: "11. Contacto",
    s11Body: "Puede enviarnos sus dudas sobre estos términos a través de la página de contacto.",
    reviewNote:
      "Estos términos se ofrecen de buena fe y en lenguaje sencillo. No constituyen asesoramiento jurídico; si necesita asesoramiento sobre su situación, consulte a un profesional cualificado.",
  },
  privacy: {
    title: "Política de privacidad",
    updated: "Última actualización",
    updatedValue: "Agosto de 2026",
    intro:
      "Aquí se explica qué datos personales recoge {businessName}, por qué y qué puede hacer al respecto. Recogemos lo mínimo que el servicio necesita para funcionar, y esta página describe lo que el software hace realmente, no lo que diría una plantilla.",
    s1Title: "1. Quién es responsable",
    s1Body:
      "{businessName}, con sede en Gibraltar, es el responsable del tratamiento de los datos personales descritos aquí. El servicio lo gestiona un único operador. Puede contactarnos a través de la página de contacto.",
    s2Title: "2. Qué recogemos",
    s2Body:
      "Para gestionar su cuenta: su dirección de correo electrónico y, salvo que inicie sesión con Google, una contraseña almacenada de forma cifrada. Opcionalmente, un nombre para mostrar. También registramos cuándo aceptó los términos y qué versión, si dio su consentimiento para recibir comunicaciones comerciales y cuándo inició sesión por última vez. Si inicia sesión con Google, le pedimos a Google únicamente dos cosas — su dirección de correo verificada y el identificador de cuenta que nos permite reconocerle la próxima vez. Nunca recibimos su contraseña de Google. Sobre sus cartas: el juego, el nombre, la colección y el número que introduce, las imágenes que sube o que producimos al escanear una carta que nos envía, el análisis derivado de ellas y el informe. Si utiliza el formulario de contacto: su nombre, su correo electrónico, el asunto, el mensaje, el idioma en el que escribió y la dirección IP desde la que se envió, que conservamos para hacer frente al uso abusivo del formulario. También guardamos un registro de auditoría de las acciones realizadas sobre los envíos. Su navegador almacena su testigo de sesión y sus preferencias de idioma y marca en su propio dispositivo; no son cookies y no se usan para rastrearle. No usamos publicidad ni analítica de seguimiento, y nunca vemos los datos de su tarjeta de pago.",
    s3Title: "3. Para qué lo usamos, y con qué base",
    s3Body:
      "Usamos su correo electrónico para gestionar su cuenta, confirmar que es suyo e informarle sobre sus propios envíos. Usamos los datos y las imágenes de sus cartas para elaborar el análisis y el informe que solicitó. Ambas cosas son necesarias para prestar el servicio que pidió. Conservamos los registros de auditoría, y la dirección IP asociada a un mensaje de contacto, para proteger el servicio frente a abusos y mantener un registro fiel de lo ocurrido — nuestro interés legítimo como operador. Las comunicaciones comerciales, si alguna vez enviamos alguna, se dirigen solo a quienes lo hayan aceptado, y puede retirar ese consentimiento desde su página de cuenta en cualquier momento.",
    s4Title: "4. Sus imágenes de cartas",
    s4Body:
      "Las imágenes que sube se utilizan para elaborar su informe y para nada más. No se venden, no se publican y no se usan para promocionar el servicio ni para entrenar nada sin pedirle permiso antes y por separado. Una fotografía tomada con un móvil suele llevar metadatos EXIF, que pueden incluir las coordenadas GPS del lugar donde se tomó — a menudo el domicilio de alguien. Cada imagen se descodifica y se vuelve a codificar en cuanto llega, lo que descarta esos metadatos antes de escribir nada en disco: conservamos la fotografía y no el lugar donde se tomó. La rotación registrada en esos metadatos se aplica primero a los píxeles, de modo que nada se almacena de lado. Aparte de eso, puede optar por publicar un informe terminado en un enlace privado. Mientras esa opción esté activada, cualquiera que tenga el enlace puede leer el informe y ver sus imágenes sin iniciar sesión. La página pide a los buscadores que no la indexen, pero un enlace que usted haya difundido escapa a nuestro control hasta que desactive la opción de compartir, lo que lo revoca de forma inmediata y definitiva.",
    s5Title: "5. Cuánto tiempo lo conservamos",
    s5Body:
      "Los envíos, escaneos, análisis e informes se conservan mientras su cuenta siga abierta, para que pueda volver a ellos; no hay caducidad automática, y puede eliminar cualquier envío concreto o su cuenta entera cuando quiera. Los mensajes del formulario de contacto se eliminan automáticamente doce meses después de enviarse. Las copias de seguridad son el único lugar donde el material eliminado permanece, y preferimos decirlo con claridad a insinuar lo contrario: se realiza una copia de la base de datos y de los archivos almacenados en el propio servidor, y se conserva 14 días antes de eliminarse. Esas copias locales no están cifradas, e incluyen los PDF de los informes, que llevan impresa la dirección de correo de la cuenta. Así que un envío o una cuenta que elimine hoy puede seguir existiendo en una copia de seguridad hasta 14 días después. Si alguna vez restauráramos desde una de ellas, volvemos a aplicar las eliminaciones realizadas desde que se tomó. Estamos trabajando en una copia cifrada y externa con 30 días de conservación; esta página cambiará el día en que eso empiece a funcionar, y todavía no funciona.",
    s6Title: "6. Eliminar su cuenta y sus datos",
    s6Body:
      "No necesita escribir a nadie. Eliminar un envío concreto desde su panel borra sus escaneos, su análisis, su informe y todas las imágenes derivadas de él, de la base de datos y del disco, de inmediato. Cerrar su cuenta desde la página de cuenta hace lo mismo con todos sus envíos y después elimina la cuenta en sí — su dirección de correo, su contraseña cifrada, su vínculo de acceso con Google si lo tiene y sus preferencias. Es una eliminación real, no una marca en una fila que se queda ahí. Conservamos el registro de auditoría de lo ocurrido, porque protege la integridad del servicio, pero se le retira la identidad: las entradas ya no le nombran, y a los dos tipos de entrada que registraban una dirección de correo en su contenido se les retira como parte de la misma operación. Nada de esto se puede deshacer, y la salvedad de las copias de seguridad de la sección anterior es la única excepción.",
    s7Title: "7. Quién más lo ve",
    s7Body:
      "Nadie, salvo el operador del servicio. No vendemos datos personales ni los compartimos con compañías de calificación. El servicio funciona en equipos propiedad del operador y no en una empresa de alojamiento, de modo que sus imágenes no están en la nube de un tercero. Hay tres proveedores inevitablemente implicados, y se nombran aquí en lugar de ocultarse tras una cláusula genérica: Cloudflare transporta el tráfico entre su navegador y el servicio, y ve la conexión y su dirección IP; un proveedor de correo entrega los mensajes que le enviamos, y ve su dirección y el contenido de esos mensajes; y Google, solo si elige iniciar sesión con Google, lo que les indica que usa este servicio. Más allá de eso, solo revelamos datos personales cuando la ley nos obliga.",
    s8Title: "8. Sus derechos",
    s8Body:
      "Conforme a la legislación de protección de datos de Gibraltar, puede solicitar una copia de sus datos, pedir que los corrijamos, pedir que los eliminemos, oponerse a determinados tratamientos o pedir que los limitemos, y solicitar sus datos en un formato portátil. La eliminación puede hacerla usted mismo, de inmediato, tal como se describe arriba. Para una copia o una exportación, contáctenos — todavía no hay un botón de autoservicio para eso, así que la preparamos a mano, y responderemos dentro del plazo legal. Si no está conforme con cómo gestionamos una solicitud, puede reclamar ante la Gibraltar Regulatory Authority.",
    s9Title: "9. Seguridad",
    s9Body:
      "Las contraseñas se almacenan cifradas, nunca en texto plano. Cambiar su contraseña, o restablecerla, cierra todas las demás sesiones abiertas a su nombre. El acceso a los envíos y a las imágenes está restringido a la cuenta propietaria y al operador, y un informe compartido por enlace solo es accesible mediante un testigo aleatorio largo que no revela nada sobre la cuenta que hay detrás. Dos cosas conviene saberlas en lugar de pasarlas por alto: su testigo de sesión se guarda en el almacenamiento de su navegador, al que podría llegar un fallo grave de tipo cross-site scripting, y las copias de seguridad en el servidor descritas en la sección 5 no están cifradas. Ningún sistema es perfectamente seguro, pero mantenemos el acceso restringido y los datos almacenados al mínimo.",
    s10Title: "10. Cambios",
    s10Body:
      "Si esta política cambia, la fecha al inicio de esta página cambia con ella. Los cambios sustanciales que afecten al uso de sus datos se le comunicarán.",
    reviewNote:
      "Esta política está redactada en lenguaje sencillo y no en jerga jurídica, y describe el software tal y como se comporta actualmente. No constituye asesoramiento jurídico; si necesita asesoramiento sobre su situación, consulte a un profesional cualificado.",
  },
  refunds: {
    title: "Política de reembolsos",
    updated: "Última actualización",
    updatedValue: "Agosto de 2026",
    intro:
      "Cuándo puede cancelar un servicio de pago de {businessName}, cuándo puede recuperar su dinero y a partir de qué momento ya no. Forma parte de nuestros Términos y condiciones.",
    s1Title: "1. Qué cubre",
    s1Body:
      "Esta política cubre los servicios que usted paga. El análisis de imagen gratuito no cuesta nada y por tanto no hay nada que reembolsar — si está usando la cuota gratuita, nada de esto le afecta. Nada se compra a través de este sitio web: no hay pasarela de pago, así que cada servicio de pago se acuerda con usted directamente y el precio se fija antes de iniciar cualquier trabajo.",
    s2Title: "2. Su derecho de desistimiento",
    s2Body:
      "Dispone de 14 días desde el día en que acordamos prestarle un servicio para cambiar de opinión y cancelarlo, sin necesidad de justificación. Avísenos a través de la página de contacto dentro de ese plazo y le reembolsaremos lo pagado, con las salvedades de las dos secciones siguientes.",
    s3Title: "3. Si nos pide empezar de inmediato",
    s3Body:
      "La mayoría de la gente quiere su informe pronto, así que normalmente empezaremos en cuanto haya pagado. Si nos pide empezar dentro del plazo de 14 días, está aceptando que el trabajo pueda iniciarse de inmediato, y de ello se derivan dos cosas. Una vez el servicio se ha prestado por completo, el derecho de desistimiento se agota y no hay reembolso. Si cancela cuando solo está parcialmente hecho, le reembolsamos lo pagado menos un importe proporcional al trabajo ya realizado. Se lo indicaremos en el momento en que nos pida empezar, para que nunca sea una sorpresa.",
    s4Title: "4. Análisis de imagen e informes",
    s4Body:
      "Un informe digital se considera prestado por completo en el momento en que se le entrega — no podemos recuperarlo, y usted ya ha recibido aquello por lo que pagó. Por eso un análisis de pago es reembolsable íntegramente hasta que empezamos a trabajar en él, y no después. Si cancela tras pagar pero antes de que empecemos, se le devuelve todo.",
    s5Title: "5. Cartas físicas enviadas a nosotros",
    s5Body:
      "Cuando nos envía una carta por correo para que la tratemos, puede cancelar y recibir el reembolso íntegro de la tarifa del servicio en cualquier momento antes de que empecemos a escanearla, y le devolveremos la carta. Una vez iniciado el escaneo el servicio está en curso y se aplica la sección 3. Los gastos de envío hasta nosotros corren de su cuenta y no son reembolsables, puesto que ya se han gastado. Cuando devolvemos una carta porque usted canceló, asumimos los gastos de devolución; cuando una carta se devuelve por cualquier otro motivo, los gastos de devolución se acuerdan con usted de antemano.",
    s6Title: "6. Restauración y otros trabajos irreversibles",
    s6Body:
      "La restauración no se puede deshacer, por lo que se trata de forma distinta y a propósito. Solo se lleva a cabo después de que hayamos expuesto lo que se propone y usted lo haya aceptado por escrito, y una vez iniciado ese trabajo no es reembolsable. Los riesgos — incluido que una carta restaurada pueda calificarse como alterada, o ser rechazada de plano por una compañía de calificación — se le explican antes de que acepte, no después.",
    s7Title: "7. Si algo ha salido mal",
    s7Body:
      "Esto es independiente de cambiar de opinión y no está limitado por las secciones anteriores. Si un servicio no se prestó con la diligencia y competencia debidas, si no entregamos lo acordado o si cometimos un error, díganoslo y lo subsanaremos — rehaciendo el trabajo o reembolsándolo, según corresponda. Que un informe llegue a una conclusión con la que usted no esté de acuerdo no es por sí mismo un defecto: nuestros informes son estimaciones y los Términos explican qué son y qué no. Un informe elaborado a partir de la carta equivocada, o uno que nunca entregamos, evidentemente sí lo es. Nada de lo aquí dispuesto afecta a sus derechos legales.",
    s8Title: "8. Cómo solicitarlo y cuánto tarda",
    s8Body:
      "Solicítelo a través de la página de contacto, indicando qué servicio pagó y, si dispone de él, el código de envío. Le confirmaremos si procede el reembolso en un plazo de cinco días hábiles. Los reembolsos aprobados se devuelven por el mismo medio con el que pagó, en un plazo de 14 días desde que los aceptamos. No cobramos ninguna comisión por tramitar un reembolso.",
    reviewNote:
      "Esta política está redactada en lenguaje sencillo y no en jerga jurídica. No constituye asesoramiento jurídico ni reduce ningún derecho que le corresponda conforme a la legislación de consumo de Gibraltar; si necesita asesoramiento sobre su situación, consulte a un profesional cualificado.",
  },
};
