import type { Dictionary } from "./en";

export const es: Dictionary = {
  common: {
    retry: "Reintentar",
  },
  nav: {
    admin: "Administración",
    dashboard: "Panel",
    logout: "Cerrar sesión",
    login: "Iniciar sesión",
    register: "Registrarse",
    menu: "Menú",
    openMenu: "Abrir menú",
    closeMenu: "Cerrar menú",
    about: "Nosotros",
    services: "Servicios",
    howItWorks: "Cómo funciona",
    contact: "Contacto",
    terms: "Términos",
    privacy: "Privacidad",
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
      "Card Care Center es un servicio independiente de pre-calificación para juegos de cartas coleccionables. Envíenos sus cartas y analizaremos el centrado, las esquinas, los bordes y la superficie, para mostrarle exactamente cómo es probable que PSA, BGS, CGC y TAG traten cada una antes de que pague por un envío real.",
    getStarted: "Comenzar",
    login: "Iniciar sesión",
    feature1Title: "Análisis automatizado",
    feature1Body:
      "Cada envío recibe una medición del centrado, detección de desgaste en esquinas y bordes, y un análisis de textura de superficie, con imágenes anotadas que muestran exactamente lo que se detectó.",
    feature2Title: "Comparación entre compañías",
    feature2Body:
      "PSA, BGS, CGC y TAG no califican de la misma manera. Destacamos los puntos específicos de discrepancia que podrían influir en el trato de su carta en cada compañía, sin prometer nunca una calificación numérica.",
    feature3Title: "Siga cada envío",
    feature3Body:
      "Cree un envío, mándenos su carta y véala avanzar desde la recepción hasta un informe descargable, todo desde su panel.",
    noteTitle: "Nota importante",
    noteBody:
      "Card Care Center es una estimación independiente, no está afiliada, respaldada ni garantiza el resultado de PSA, Beckett Grading Services (BGS), CGC, TAG ni ninguna otra compañía de calificación externa. Los escaneos se capturan con un escáner plano, que utiliza luz difusa en lugar de luz rasante; el análisis de superficie en particular tiene menor confiabilidad que lo que puede detectar la fotografía especializada de una compañía de calificación.",
  },
  login: {
    title: "Iniciar sesión",
    email: "Correo electrónico",
    password: "Contraseña",
    submit: "Iniciar sesión",
    submitting: "Iniciando sesión…",
    failed: "Error al iniciar sesión",
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
      "{count} hallazgo(s) detectado(s) automáticamente descartado(s). Las puntuaciones reflejan sus cambios, y el informe se etiquetará claramente como ajustado por el cliente.",
    deleteButton: "Eliminar envío",
    deleteTitle: "¿Eliminar este envío?",
    deleteBody:
      "Esto elimina permanentemente el envío, sus escaneos, el análisis y cualquier informe. No se puede deshacer.",
    deleteConfirm: "Eliminar permanentemente",
    deleteCancel: "Cancelar",
    deleteFailed: "No se pudo eliminar el envío.",
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
  upload: {
    title: "Suba las fotos de su carta",
    subtitle: "Añada una foto clara de cada lado, o escanéela con la cámara de su dispositivo.",
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
  cropAdjust: {
    title: "Confirme las esquinas de la carta",
    instructions: "Arrastre los 4 controles hasta las esquinas exactas de la carta y confirme.",
    confirmButton: "Confirmar recorte",
    confirming: "Confirmando…",
    loadFailed: "No se pudo cargar la foto para recortar.",
    confirmFailed: "No se pudo confirmar el recorte.",
    snapButton: "Ajustar a los bordes detectados",
    snapFailed: "No se pudo refinar el recorte.",
    rotateLeft: "Girar a la izquierda",
    rotateRight: "Girar a la derecha",
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
    lede: "Un coleccionista local que quiere que cuidar sus cartas deje de ser una lotería.",
    body1:
      "Card Care Center nació en Gibraltar, y lo lleva alguien que colecciona lo mismo que usted. Quien haya enviado una carta a calificar conoce la sensación: paga la tarifa, envía algo que le importa, espera semanas, y solo entonces descubre si mereció la pena.",
    body2:
      "Ese hueco es lo que este servicio pretende cerrar. Antes de comprometerse con un envío, obtiene una lectura medida del centrado, las esquinas, los bordes y la superficie, con imágenes anotadas que muestran exactamente qué se detectó y por qué. Si la carta no va a calificar como esperaba, mejor saberlo aquí que después de pagar un envío real.",
    body3:
      "El objetivo más amplio es facilitar el coleccionismo, el cuidado y la calificación de cartas a la gente de Gibraltar y alrededores: un sitio cercano donde preguntar, donde revisen una carta como es debido y, con el tiempo, donde entregarla para calificación sin tener que enviarla usted mismo.",
    honestTitle: "Hablando claro",
    honestBody:
      "Esto es una estimación, no un veredicto. El análisis automático detecta mucho, pero un escaneo plano usa luz difusa en lugar de la luz rasante que emplea una compañía de calificación, así que puede pasar por alto defectos sutiles de superficie y, en ocasiones, marcar la textura de impresión como un defecto. Puede descartar cualquier hallazgo que considere erróneo, y cada informe dice con claridad qué es y qué no es.",
    ctaTitle: "¿Tiene una carta que le genera dudas?",
    ctaBody: "Haga una revisión gratuita y vea el resultado antes de comprometerse a nada.",
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
    pricingNote:
      "Los precios de los servicios de pago aún no están fijados. Nada de esta página le compromete a nada, y no se trabaja sobre ninguna carta sin acordar antes el coste con usted.",
    tier1Name: "Análisis de imagen e informe",
    tier1Body:
      "El servicio que ya funciona hoy, gratuito y con un límite de cartas revisadas. Suba una foto o envíenos la carta, y reciba un desglose completo.",
    tier1Point1: "Análisis medido de centrado, esquinas, bordes y superficie",
    tier1Point2: "Imágenes anotadas que muestran exactamente qué se marcó y dónde",
    tier1Point3:
      "Notas comparativas sobre cómo suelen tratar esos hallazgos PSA, BGS, CGC y TAG",
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
      "Suba una foto nítida y plana del frente (y del reverso si lo tiene), o envíenos la carta y la escanearemos como es debido. Usted confirma el recorte para que las medidas se tomen de la carta y no del fondo.",
    step3Title: "Se ejecuta el análisis",
    step3Body:
      "El centrado se mide a partir del ancho de los márgenes, se revisan esquinas y bordes en busca de blanqueo y desgaste, y se examina la superficie buscando arañazos y dobleces. Normalmente tarda unos instantes.",
    step4Title: "Lea su informe",
    step4Body:
      "Recibe una puntuación por categoría, imágenes anotadas que señalan cada hallazgo, y notas sobre cómo suelen tratarlos las principales compañías. Puede descartar lo que considere erróneo, y el informe indicará con claridad que fue ajustado.",
    faqTitle: "Preguntas frecuentes",
    faq1Q: "¿Es una calificación oficial?",
    faq1A:
      "No. Es una estimación independiente para ayudarle a decidir si enviar la carta. No estamos afiliados a PSA, BGS, CGC, TAG ni a ninguna otra compañía, y nunca predecimos una calificación numérica en su nombre.",
    faq2Q: "¿Qué precisión tiene?",
    faq2A:
      "El centrado se mide y es el más fiable de los cuatro. Esquinas y bordes funcionan bien. La superficie es el punto débil: un escaneo plano usa luz difusa, mientras que una compañía de calificación usa luz rasante que proyecta sombras en los arañazos, así que pueden pasarse por alto defectos leves y a veces se marca la textura de impresión.",
    faq3Q: "¿Por qué marcó algo que no existe?",
    faq3A:
      "Normalmente texto o textura de impresión leídos como un arañazo, o un recorte que entró dentro de la carta. Puede descartar cualquier hallazgo con el que no esté de acuerdo y las puntuaciones se actualizan al instante. El informe pasa entonces a indicar claramente que usted lo ajustó.",
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
    ctaBody: "La primera revisión es gratuita.",
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
  },
  terms: {
    title: "Términos y condiciones",
    updated: "Última actualización",
    updatedValue: "Julio de 2026",
    intro:
      "Estos términos regulan su uso de Card Care Center. Al crear una cuenta o enviar una carta, los acepta. Lea en particular el aviso siguiente.",
    disclaimerTitle: "Aviso importante",
    disclaimerBody:
      "Card Care Center es una estimación independiente. No está afiliada, respaldada ni garantiza el resultado de PSA, Beckett Grading Services (BGS), CGC, TAG ni ninguna otra compañía de calificación externa. Nada de lo que producimos es una calificación, una predicción de calificación ni una promesa sobre lo que decidirá ninguna compañía. Una carta con buena puntuación aquí puede calificar por debajo de lo esperado, y al revés.",
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
      "Puede descartar hallazgos concretos que considere incorrectos, y las puntuaciones se actualizan en consecuencia. Todo informe en el que lo haya hecho queda etiquetado como ajustado por el cliente, y se muestran tanto la puntuación original como la ajustada. Usted es responsable de los ajustes que realice, y un informe ajustado no debe presentarse a terceros como una evaluación sin modificar.",
    s5Title: "5. Su cuenta",
    s5Body:
      "Debe facilitar una dirección de correo válida y mantener su contraseña segura. Usted es responsable de la actividad realizada desde su cuenta. No suba imágenes sobre las que no tenga derechos, ni contenido ilícito. Podemos suspender o cerrar una cuenta que se esté utilizando indebidamente.",
    s6Title: "6. Cartas físicas",
    s6Body:
      "Cuando nos envíe una carta, la tratamos con cuidado y reducimos la manipulación al mínimo. No se hace nada a una carta física más allá de escanearla salvo que usted lo haya solicitado expresamente y lo hayamos acordado por escrito. El envío hasta nosotros y el seguro en tránsito por el valor que considere adecuado corren de su cuenta. Los trabajos de restauración, cuando se acuerden, conllevan un riesgo inherente de daño y una carta restaurada puede ser calificada como alterada o rechazada por una compañía de calificación; ese riesgo se explica y se acuerda antes de comenzar cualquier trabajo.",
    s7Title: "7. Tarifas",
    s7Body:
      "El análisis básico de imagen es actualmente gratuito, sujeto a límites de uso razonable. Los servicios de pago se describen en la página de Servicios; cuando un servicio figura como próximamente o previsto, todavía no está disponible para su contratación. Las tarifas de cualquier servicio de pago se acuerdan con usted antes de iniciar el trabajo.",
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
    updatedValue: "Julio de 2026",
    intro:
      "Aquí se explica qué datos personales recoge Card Care Center, por qué, y qué puede hacer al respecto. Recogemos lo mínimo que el servicio necesita para funcionar.",
    s1Title: "1. Quién es responsable",
    s1Body:
      "Card Care Center, con sede en Gibraltar, es el responsable del tratamiento de los datos personales aquí descritos. Puede contactarnos a través de la página de contacto.",
    s2Title: "2. Qué recogemos",
    s2Body:
      "Su dirección de correo y una contraseña almacenada de forma cifrada, para que pueda iniciar sesión. Los datos de las cartas que envía: juego, nombre, edición y número. Las imágenes que sube o que generamos al escanear su carta, junto con el análisis derivado de ellas. Registros básicos de las acciones realizadas sobre sus envíos, para mantener una traza de auditoría. No recogemos datos de tarjetas de pago en este sitio, y no usamos cookies publicitarias ni de seguimiento.",
    s3Title: "3. Para qué los usamos, y con qué base",
    s3Body:
      "Usamos su correo para gestionar su cuenta, verificarla y enviarle avisos sobre sus propios envíos. Usamos los datos de sus cartas y sus imágenes para elaborar el análisis y el informe que solicitó. Ambos son necesarios para prestar el servicio que pidió. Conservamos registros de auditoría para proteger la integridad del servicio, lo que constituye nuestro interés legítimo como operador.",
    s4Title: "4. Sus imágenes",
    s4Body:
      "Las imágenes que sube se usan para elaborar su informe y para nada más. No se venden, no se publican, y no se emplean para promocionar el servicio ni para entrenar nada sin pedírselo antes y por separado. Se almacenan para que su informe siga funcionando cuando lo abra más adelante.",
    s5Title: "5. Cuánto tiempo los conservamos",
    s5Body:
      "Los envíos, escaneos, análisis e informes se conservan mientras su cuenta esté activa, para que pueda volver a ellos. Eliminar un envío borra sus escaneos, análisis e informe de forma permanente e inmediata. Si nos pide cerrar su cuenta, eliminaremos sus datos personales, conservando únicamente lo que estemos legalmente obligados a retener.",
    s6Title: "6. Quién más los ve",
    s6Body:
      "Nadie, salvo el operador del servicio. No vendemos datos personales y no los compartimos con compañías de calificación ni con ningún tercero, salvo cuando un proveedor sea estrictamente necesario para prestar el servicio (como el alojamiento o el envío de correo), o cuando estemos legalmente obligados a comunicarlos.",
    s7Title: "7. Sus derechos",
    s7Body:
      "Conforme a la normativa de protección de datos de Gibraltar puede solicitar una copia de sus datos, pedir que los corrijamos, pedir que los eliminemos, oponerse o solicitar la limitación de determinados tratamientos, y pedir sus datos en un formato portátil. Contáctenos y responderemos dentro del plazo legal. Si no está conforme con cómo gestionamos una solicitud, puede reclamar ante la Gibraltar Regulatory Authority.",
    s8Title: "8. Seguridad",
    s8Body:
      "Las contraseñas se almacenan cifradas, nunca en texto plano. El acceso a los envíos y las imágenes está restringido a la cuenta propietaria y al operador. Ningún sistema es perfectamente seguro, pero mantenemos el acceso restringido y los datos almacenados al mínimo.",
    s9Title: "9. Cambios",
    s9Body:
      "Si esta política cambia, la fecha del inicio de la página cambia con ella. Los cambios relevantes que afecten al uso de sus datos se le comunicarán.",
    reviewNote:
      "Esta política está redactada en lenguaje sencillo y no como texto jurídico estándar. No constituye asesoramiento legal; si necesita asesoramiento sobre su situación, consulte a un profesional cualificado.",
  },
};
