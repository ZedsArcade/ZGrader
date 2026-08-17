export const en = {
  common: {
    retry: "Retry",
  },
  nav: {
    admin: "Admin",
    dashboard: "Dashboard",
    account: "Account",
    logout: "Log out",
    login: "Log in",
    register: "Register",
    menu: "Menu",
    openMenu: "Open menu",
    closeMenu: "Close menu",
    about: "About",
    services: "Services",
    pricing: "Pricing",
    howItWorks: "How it works",
    methodology: "Methodology",
    contact: "Contact",
    terms: "Terms",
    privacy: "Privacy",
  },
  status: {
    created: "Created",
    awaiting_scans: "Awaiting scans",
    processing: "Processing",
    draft_ready: "Draft ready",
    approved: "Approved",
    published: "Published",
    error: "Error",
  },
  category: {
    centering: "Centering",
    corners: "Corners",
    edges: "Edges",
    surface: "Surface",
  },
  severity: {
    none: "None",
    minor: "Minor",
    major: "Major",
  },
  landing: {
    title: "Know before you submit.",
    subtitle:
      "{businessName} is an independent pre-grading service for trading card games. Send us your cards, and we'll scan and analyze centering, corners, edges, and surface, then show you exactly how {companies} are likely to treat each one before you pay to submit for real.",
    getStarted: "Get started",
    login: "Log in",
    feature1Title: "Automated analysis",
    feature1Body:
      "Every submission gets a measured centering ratio, corner and edge wear detection, and a surface texture pass -- with annotated images showing exactly what was flagged.",
    feature2Title: "Multi-company comparison",
    feature2Body:
      "{companies} don't grade the same way. We highlight the specific points of contention that could sway your card's treatment differently at each company -- never a promised numeric grade.",
    feature3Title: "Track every submission",
    feature3Body:
      "Create a submission, ship us your card, and watch it move from received to a downloadable report -- all from your dashboard.",
    // Fills the {companies} placeholders above when every company has been
    // disabled, so the sentences still read properly.
    companiesFallback: "the major grading companies",
    noteTitle: "An important note",
    noteBody:
      "{businessName} is an independent estimate, not affiliated with, endorsed by, or a guarantee of the outcome from PSA, Beckett Grading Services (BGS), CGC, TAG, ACE, or any other third-party grading company. Scans are captured on a flatbed scanner, which uses diffuse rather than raking light -- surface analysis in particular is lower-confidence than what a specialized grading company's photography can catch.",
  },
  login: {
    title: "Log in",
    email: "Email",
    password: "Password",
    submit: "Log in",
    submitting: "Logging in…",
    failed: "Login failed",
    forgotPassword: "Forgotten your password?",
  },
  register: {
    title: "Create an account",
    subtitle: "Register to submit cards and track your reports.",
    email: "Email",
    password: "Password",
    passwordHint: "At least 8 characters.",
    submit: "Register",
    submitting: "Creating account…",
    failed: "Registration failed",
    acceptTerms: "I agree to the Terms & Conditions and the Privacy Policy",
    acceptTermsRequired: "Please accept the terms to create an account.",
    termsLink: "Terms & Conditions",
    privacyLink: "Privacy Policy",
    marketingOptIn: "Email me occasional updates about new services (optional)",
    checkInbox:
      "Check your inbox -- we've sent a link to confirm your email address. You'll need it before you can submit a card.",
  },
  verify: {
    title: "Email verification",
    verifying: "Verifying…",
    success: "Your email is verified. You can now",
    loginLink: "log in",
    failed: "Verification failed",
  },
  dashboard: {
    title: "Your submissions",
    subtitle: "Track every card you've sent in for pre-grading.",
    newSubmission: "New submission",
    loadFailed: "Failed to load submissions",
    emptyTitle: "No cards graded yet",
    emptyDescription: "Track every card you've sent in for pre-grading, right here.",
    emptyCta: "Scan your first card",
    colCode: "Code",
    colStatus: "Status",
    colCreated: "Created",
    view: "View",
  },
  newSubmission: {
    title: "New submission",
    subtitle: "Tell us about the card, then ship it to us for scanning.",
    game: "Game",
    dimensionsUnverified: " (dimensions unverified)",
    cardName: "Card name",
    setName: "Set (optional)",
    cardNumber: "Card number (optional)",
    foil: "Foil / holo",
    submit: "Create submission",
    submitting: "Creating…",
    failed: "Failed to create submission",
    gamesLoadFailed: "Failed to load games",
  },
  submissionDetail: {
    createdOn: "Created",
    download: "Download report",
    downloading: "Downloading…",
    downloadFailed: "Report not available yet",
    loadFailed: "Failed to load submission",
    unknownCard: "Unknown card",
    foilLabel: "Foil",
    lowerConfidence: "lower confidence",
    // Axis labels for the centering splits shown beside the score, so the
    // number has something visible behind it. Kept to initials because they sit
    // in a small card next to four figures; the methodology page spells out
    // what is being measured.
    leftRightShort: "L/R",
    topBottomShort: "T/B",
    // Shown instead of a number when the pipeline declined to score a
    // category. Deliberately not "0" or "N/A" -- it should read as a decision
    // we made, not as data that went missing.
    unmeasurable: "Not measurable",
    // Keyed by the limitation codes in backend analysis/assessment.py. Stored
    // as codes so the wording can change here without re-analysing any card.
    limitation: {
      card_is_foil:
        "You told us this card is foil or holo, which interferes with every measurement here — so all of them are held to a wider range.",
      surface_no_detail:
        "This photo has no fine detail on the card's face, so a scratch couldn't have shown up either — surface wasn't scored.",
      surface_diffuse_light:
        "Lit evenly rather than at an angle, so faint scratches can be missed.",
      corners_whitening_only:
        "The card's outline couldn't be established, so only discolouration was checked — a corner worn blunt but not discoloured isn't caught.",
      corners_pale_border:
        "This border is pale, so the colour half of the corner check has little to work with. Missing material is still measured.",
      centering_no_frame:
        "No clear printed border to measure against — normal on full-art cards.",
      centering_partial_frame:
        "A printed border was found on some sides but not all, so this rests on fewer edges than usual.",
      edges_partial: "Some edges couldn't be sampled and were left out of this score.",
      edges_thin_border:
        "This card's border is too narrow to sample clean card beside the cut, so those edges were judged on the straightness of the cut alone.",
      capture_too_low_resolution:
        "The card is too small in this photo for wear at this scale to be visible — a closer photo would let it be measured.",
      capture_modest_resolution:
        "Big enough in frame to show obvious damage, not to judge fine wear — so this reading is held to a wider range.",
      // Leads with the fix, not the diagnosis. Measured across 30 real
      // photographs: 8 of the 10 that failed this check were recovered by a
      // crop traced tightly around the card, and only 2 needed a new photo.
      // The second sentence is for the 2 of 10 a re-crop cannot save.
      // The detector finds the card by contrast against whatever is behind
      // it, so a dark card back on a dark surface leaves it nothing to fit a
      // line to, and no amount of re-cropping adds contrast that was never
      // captured. Without it the one customer who cannot be rescued is told
      // to do the only thing that will not work.
      geometry_unverified:
        "The card's edges couldn't be located in this image, so there was nothing reliable to measure from. Usually it's the crop — drag the handles so they sit tightly around the card, with none of the background inside them, and submit again. If that doesn't help, the card and the surface behind it were probably too close in tone to tell apart: photograph it again on a plain background that contrasts with the card.",
      geometry_aspect_mismatch:
        "The measured area isn't the shape of a card, so the millimetre figures are scaled wrong on at least one axis.",
      combined_single_side:
        "Only one face could be read for this category, so this rests on that face alone rather than both — a narrower view of the card, not a worse one.",
    },
    comparisonTitle: "Multi-company comparison",
    comparisonSubtitle:
      "Points of contention that may affect how each company treats this card. This is not a predicted numeric grade from any company.",
    colCompany: "Company",
    colAssessment: "Assessment",
    colNotes: "Notes",
    awaitingScansTitle: "Waiting for your card to be scanned",
    processingTitle: "Analysing card…",
    processingDescription: "This usually only takes a moment.",
    photoTitle: "Analyzed photo",
    adjustedChip: "Adjusted",
    originalScorePrefix: "was",
    adjustedBannerTitle: "You've adjusted this assessment",
    adjustedBannerBody:
      "{count} auto-detected finding(s) dismissed. Where a score can still be re-derived from the findings that remain, it has been; where dismissing left nothing to measure from, the original measurement stands. Either way the report will be clearly labelled as client-adjusted.",
    deleteButton: "Delete submission",
    deleteTitle: "Delete this submission?",
    deleteBody:
      "This permanently deletes the submission, its scans, analysis, and any report. This cannot be undone.",
    deleteConfirm: "Delete permanently",
    deleteCancel: "Cancel",
    deleteFailed: "Couldn't delete the submission.",
    // The share panel on the customer's own detail page.
    shareTitle: "Share this report",
    shareBody:
      "Turn this on to get a link anyone can open, with no account and no sign-in. It shows the card, the scores and the findings -- never your email, your account or the submission code.",
    shareUnavailable: "You can share a report once it's published.",
    shareEnable: "Create a share link",
    shareEnabling: "Creating…",
    shareCopy: "Copy link",
    shareCopied: "Copied",
    // "Rotate" is jargon; what a customer wants to know is that the old link
    // dies. Say that, since it is the destructive half of the control.
    shareRotate: "Replace link",
    shareRotateBody: "The old link stops working immediately. Anyone still holding it sees nothing.",
    shareDisable: "Stop sharing",
    shareDisabledNote: "Sharing is off. Nobody can open this report without signing in.",
    shareFailed: "Couldn't change the share setting.",
  },
  breakout: {
    front: "Front",
    back: "Back",
    zoomedViewLabel: "Zoomed view",
    okChip: "OK",
    flaggedChip: "Flagged",
    noRegionsNote: "Nothing was flagged on this side.",
    showMore: "Show {count} more issue(s)",
    showLess: "Show less",
    lowConfidenceNote: "Centering could not be measured reliably on this card.",
    lowConfidenceGenericNote:
      "Lower-confidence detection -- flat scan light catches only pronounced defects here. Dismiss it if you disagree.",
    dismiss: "Dismiss",
    restore: "Restore",
    dismissedBadge: "Dismissed",
    toggleFailed: "Couldn't update the assessment.",
    aiObservationsTitle: "AI observations (assistive, lower confidence)",
    collapse: "Collapse",
    expand: "Expand",
    collapseAll: "Collapse all",
    expandAll: "Expand all",
    whyFlagged: "Why was this flagged? How the analysis works",
  },
  inspector: {
    inspect: "Inspect photo",
    close: "Close",
    zoomIn: "Zoom in",
    zoomOut: "Zoom out",
    resetZoom: "Fit",
    hideMarkers: "Hide markings",
    showMarkers: "Show markings",
  },
  account: {
    title: "Your account",
    subtitle: "Your sign-in details and preferences.",
    emailLabel: "Email address",
    displayNameLabel: "Display name (optional)",
    displayNameHint: "How we address you in emails and reports.",
    marketingLabel: "Send me occasional updates about new services",
    marketingHint:
      "Off by default. Notifications about your own submissions are sent either way.",
    save: "Save changes",
    saving: "Saving…",
    saved: "Account updated.",
    saveFailed: "Couldn't save your changes.",
    unverified: "Your email address isn't confirmed yet.",
    resend: "Resend the confirmation email",
    resent: "If that address needs confirming, a new link is on its way.",
    changePasswordTitle: "Change password",
    currentPassword: "Current password",
    newPassword: "New password",
    changePassword: "Change password",
    changing: "Changing…",
    changed: "Password changed. You've been signed out on other devices.",
    changeFailed: "Couldn't change your password.",
    dangerTitle: "Close your account",
    dangerBody:
      "This permanently deletes your account, every submission, all scans and every report. It cannot be undone.",
    deleteButton: "Delete my account",
    deleteConfirmTitle: "Delete your account?",
    deleteConfirmBody:
      "Everything is removed immediately and permanently. There is no way to recover it.",
    deleteConfirm: "Delete permanently",
    deleteCancel: "Cancel",
    deleteFailed: "Couldn't delete your account.",
  },
  forgotPassword: {
    title: "Reset your password",
    subtitle: "Enter your email address and we'll send you a link to set a new password.",
    email: "Email",
    submit: "Send reset link",
    submitting: "Sending…",
    sent: "If that address has an account, a reset link is on its way. Check your inbox.",
    backToLogin: "Back to sign in",
  },
  resetPassword: {
    title: "Choose a new password",
    password: "New password",
    passwordHint: "At least 8 characters.",
    submit: "Set new password",
    submitting: "Saving…",
    success: "Your password has been changed. You can now sign in.",
    failed: "This reset link is invalid or has expired.",
    requestNew: "Request a new link",
    loginLink: "Sign in",
  },
  upload: {
    title: "Upload your card scans",
    subtitle: "Add a clear photo of each side, or scan it with your device's camera.",
    // The one thing the customer controls that matters most, said before they
    // shoot rather than after it fails. Edges are found by contrast against the
    // background, so a dark card on a dark surface is the case the detector
    // cannot recover -- and nothing used to mention it anywhere.
    backgroundHint:
      "Stand the card on a plain surface that contrasts with it — a dark card on a light background, a pale one on dark. That contrast is what lets the card's edges be found.",
    frontLabel: "Front (required)",
    backLabel: "Back (optional)",
    backHint: "Add now, or add it later — front alone still gets you a partial check.",
    chooseFile: "Choose photo",
    uploading: "Uploading…",
    frontUploadedTitle: "Front received",
    frontUploadedNote:
      "Your partial check is underway. Add a back image any time before it's approved for a full check, or leave it as-is.",
    uploadFailed: "Upload failed",
    invalidImage: "That doesn't look like a valid image. Try a JPEG, PNG, or TIFF.",
    fileTooLarge: "That image is too large.",
  },
  centeringAdjust: {
    toggle: "Adjust centering",
    toggleDone: "Done adjusting",
    title: "Check the centering lines",
    instructions:
      "These four lines are where the border was detected. If one is in the wrong place, drag its handle to move it â the ratios update as you go, and the score is recalculated when you apply.",
    disabled: "Adjusting the centering lines is currently switched off.",
    loadFailed: "Couldn't load the image for adjusting.",
    leftRight: "Left / right",
    topBottom: "Top / bottom",
    worstSide: "Worst side",
    apply: "Apply and rescore",
    applying: "Rescoringâ¦",
    applied: "Centering rescored from the lines you set.",
    applyFailed: "Couldn't apply that adjustment.",
    reset: "Back to detected",
    handleLabel: {
      left_px: "Left border line",
      right_px: "Right border line",
      top_px: "Top border line",
      bottom_px: "Bottom border line",
    },
  },
  cropAdjust: {
    title: "Confirm which card to analyse",
    // No longer "the exact corners". The handles used to be the geometry every
    // measurement was taken from, so precision mattered; they are now a hint
    // about where to look, and the edges are found from the card itself.
    instructions: "Drag the 4 handles roughly onto the card's corners, then confirm. They don't need to be exact — the card's edges are found automatically.",
    confirmButton: "Confirm crop",
    confirming: "Confirming…",
    loadFailed: "Couldn't load the photo for cropping.",
    confirmFailed: "Couldn't confirm the crop.",
    // Capacity, not failure. Both are recoverable by waiting, and both say so
    // rather than leaving someone to guess whether to retry.
    confirmBusy:
      "The analyser is busy right now. Your crop wasn't lost -- wait a moment and confirm again.",
    confirmAlreadyRunning:
      "You already have a card being analysed. Wait for that one to finish, then confirm this crop.",
    snapButton: "Snap to detected edges",
    snapFailed: "Couldn't refine the crop.",
    rotateLeft: "Rotate left",
    rotateRight: "Rotate right",
    // Shown before the crop is confirmed, because confirming spends the
    // submission. The explanation itself is reused from
    // submissionDetail.limitation.geometry_unverified rather than reworded --
    // one condition should not have two descriptions.
    checking: "Checking the crop…",
    boundaryWarningTitle: "The card's edges couldn't be found",
    boundaryWarningHint:
      "You can still submit, but this card would come back with no scores. Adjusting the crop fixes it far more often than retaking the photo does.",
    adjustInstead: "Let me adjust it",
    submitAnyway: "Submit anyway",
    checkFailed: "Couldn't check the crop — you can still confirm it.",
  },
  footer: {
    tagline: "Independent pre-grading for trading card games, based in Gibraltar.",
    exploreHeading: "Explore",
    legalHeading: "Legal",
    connectHeading: "Connect",
    rights: "All rights reserved.",
    instagram: "Instagram",
    facebook: "Facebook",
    x: "X",
    whatsapp: "WhatsApp",
    email: "Email us",
  },
  about: {
    title: "About us",
    lede: "A local collector trying to make grading and caring for cards less of a guessing game.",
    body1:
      "{businessName} started in Gibraltar, run by someone who collects the same things you do. Anyone who has sent a card away for grading knows the feeling: you pay the fee, you post something you care about, you wait weeks, and only then do you find out whether it was worth doing at all.",
    body2:
      "That gap is what this service exists to close, and closing it properly turned out to need two halves. One measures a card and tells you where it stands before you pay anyone to grade it. The other looks after the card itself -- handling, storage, surface cleaning, and honest advice about what restoration can and cannot safely achieve.",
    splitTitle: "Two sides, one workshop",
    splitLede:
      "Same person, same bench, two different jobs. Most people arrive for one and end up wanting the other.",
    labTitle: "{businessName}",
    labBody:
      "Knowing where a card stands. Measured centering, corners, edges and surface, with annotated images showing exactly what was picked up and why. If a card isn't going to grade the way you hoped, far better to learn that here than after paying for a real submission.",
    careTitle: "{businessName}",
    careBody:
      "Looking after the card itself. Sleeving, storage and handling, careful surface cleaning, and a frank opinion on whether anything should be done at all. Plenty of cards are best left exactly as they are, and you will be told so.",
    body3:
      "The wider aim is to make collecting, caring for, and grading cards easier for people in and around Gibraltar -- somewhere local to ask questions, get a card looked at properly, and eventually hand it over for grading without shipping it yourself.",
    honestTitle: "Being straight with you",
    honestBody:
      "This is an estimate, not a verdict. Automated analysis catches a lot, but a flatbed scan uses diffuse light rather than the raking light a grading company uses, so subtle surface defects can be missed and print texture can occasionally be flagged as a defect. You can dismiss anything you think is wrong, and every report says plainly what it is and what it isn't.",
    ctaTitle: "Have a card you're unsure about?",
    ctaBody: "Run a free check and see what comes back before you commit to anything.",
  },
  // The card-care / restoration section, served under /care with its own
  // palette. Kept as its own block rather than folded into `services` so the
  // two sides of the business can diverge in copy without stepping on each
  // other.
  googleAuth: {
    button: "Continue with Google",
    divider: "or",
    signingIn: "Signing you in…",
    oneMoment: "One moment while we finish signing you in.",
    problemTitle: "Sign-in didn't complete",
    missingToken: "That sign-in link didn't carry a session. Please try again.",
    failed: "We couldn't complete the sign-in. Please try again.",
    backToLogin: "Back to sign in",
    // Shown on the login page when the callback bounces back with a reason --
    // most often the address already having a password account.
    errorPrefix: "Google sign-in:",
  },
  quota: {
    chipRemaining: "{n} checks left",
    chipExhausted: "No checks left",
    chipExhaustedIn: "Resets in {time}",
    ariaLabel: "Checks remaining this period",
    // Short units, so the countdown fits a chip: "2d 6h", "3h 40m".
    unitDay: "d",
    unitHour: "h",
    unitMinute: "m",
    exhaustedTitle: "You've used this period's checks",
    exhaustedBody:
      "Your allowance resets automatically in {time}. A subscription removes the limit entirely.",
    exhaustedBodyNoTimer:
      "Your allowance resets automatically. A subscription removes the limit entirely.",
    seePlans: "See plans",
  },
  care: {
    title: "Looking after the card you already own.",
    lede: "Cleaning, protection and honest advice on restoration -- with the risks stated plainly before anything is touched.",
    intro:
      "{businessName} is the care side of the service. Where the analysis side tells you whether a card is worth submitting, this side is about the physical object: how it is stored, how it is handled, and what can and cannot be safely improved.",
    ctaPrimary: "Ask about a card",
    ctaSecondary: "Back to grading analysis",
    s1Title: "Handling and storage",
    s1Body:
      "Most avoidable damage happens between the card leaving a pack and reaching a sleeve. Advice here is free and specific to what you actually own, not a generic checklist.",
    s2Title: "Surface cleaning",
    s2Body:
      "Loose surface debris and fingerprints can often be dealt with safely. Anything that would alter the printed surface itself is not cleaning, and is treated as restoration below.",
    s3Title: "Restoration consultation",
    s3Body:
      "Some problems can be improved; many cannot, and some attempts make things worse. The consultation is free precisely so nobody pays to be told no.",
    servicesTitle: "Card care services",
    servicesLede:
      "Everything that involves physically handling a card you own — storage, cleaning, restoration, and getting it safely to a grading company.",
    warningTitle: "Read this before asking for restoration",
    warningBody:
      "Restoration carries real risk. A restored card may be graded as altered, or refused outright, by a grading company -- and that outcome is permanent. Nothing is attempted without discussing it with you first and agreeing it in writing. If the honest answer is to leave a card alone, that is the answer you will get.",
  },
  pricing: {
    title: "Pricing",
    subtitle:
      "Two services at launch: analysis from your own photos, and an in-hand pre-grade. Everything below is what it costs, with nothing hidden until checkout.",
    // Every figure on this page is read from the admin panel, so the copy
    // carries placeholders and never a number of its own.
    softwareHeading: "Image Analysis",
    softwareLede:
      "Upload photos of a card and get a pre-grading report -- centering, corners, edges and surface, with the risk factors flagged.",
    planFree: "Free",
    planPack: "Credit pack",
    planMonthly: "Monthly",
    planAnnual: "Annual",
    planFreeNote: "The free report is not cut down. You get the same analysis as every paid tier.",
    planPackNote: "Buy once, use over a year. For people who would rather not subscribe.",
    planMonthlyNote: "For regular use, cancel whenever.",
    planAnnualNote: "The same as monthly, paid once.",
    perMonth: "per month",
    perYear: "per year",
    oneOff: "one-off",
    checksPerPeriod: "{count} checks every {days} days",
    checksUnlimited: "Unlimited checks",
    checksOneOff: "{count} checks",
    // Quoted by the marketing pages as well as this one, which is why it lives
    // here beside the allowance strings it is built from.
    freeAllowance: "Free accounts get {allowance}.",
    freeCta: "Start a free check",
    paidCta: "Get in touch",
    // Said plainly rather than discovered at a dead end: nothing here takes
    // card payments yet, so every paid tier is arranged by conversation.
    paidNote: "Paid tiers are arranged directly at the moment -- send a message and it is set up by hand.",

    physicalHeading: "Personalised Pre-grading",
    physicalLede:
      "The card inspected in hand: scanned, measured, written up, and an honest call on whether it is worth submitting.",
    physicalQty: "Cards",
    physicalPer: "Per card",
    physicalTurnaround: "5-7 working days from receipt.",
    physicalLocation: "Gibraltar only at launch, to keep the logistics simple.",
    physicalPostage: "Return postage at cost, tracked and insured.",
    physicalCta: "Arrange a pre-grade",

    bundlesHeading: "Bundles",
    triageName: "Collection Triage",
    triageBody:
      "Bring a binder or a box. Everything gets screened, the best of it gets a physical pre-grade, and you get a written verdict: grade these, sell these raw, these are not worth the postage.",
    triageGuide: "Guide price around {price} -- jobs vary too much to quote blind.",
    triageCta: "Ask about a collection",
    doubleName: "Double Check",
    doubleBody:
      "Book a pre-grade batch of 10 or more cards and three months of the paid tier comes with it.",

    extrasHeading: "While you subscribe",
    discount: "{percent}% off any physical service for as long as your subscription runs.",
    founder: "Founder pricing: the first {seats} annual subscribers pay {price}, locked for as long as they stay.",

    // Generated from the enabled companies rather than hardcoded, so it can
    // never name one the operator has switched off.
    disclaimer:
      "No grade is guaranteed. The report is an assessment of risk factors, not a prediction that {companies} are bound by.",
  },
  services: {
    title: "Services",
    subtitle:
      "Start with a free check. Everything beyond that is being built out -- get in touch if you want something on this list before it lands.",
    statusAvailable: "Available now",
    statusComingSoon: "Coming soon",
    statusPlanned: "Planned",
    includesLabel: "Includes",
    contactCta: "Get in touch",
    startCta: "Start a free check",
    methodologyCta: "How the analysis works",
    pricingNote:
      "Pricing for the paid services isn't fixed yet. Nothing on this page commits you to anything, and no card is worked on without agreeing the cost with you first.",
    tier1Name: "Image analysis & report",
    tier1Body:
      "The service running today, free to use with a limit on how many cards you can check. Upload a photo or send us the card, and get a full breakdown back.",
    tier1Point1: "Measured centering, corner, edge and surface analysis",
    tier1Point2: "Annotated images showing exactly what was flagged and where",
    tier1Point3: "Side-by-side notes on how {companies} each tend to treat those findings",
    tier1Point4: "A downloadable PDF report you can keep",
    tier2Name: "Unlimited subscription",
    tier2Body:
      "For people going through a collection rather than checking the odd card. Everything in the free tier with the cap removed, kept deliberately cheap.",
    tier2Point1: "Unlimited card checks and reports",
    tier2Point2: "Priority processing",
    tier2Point3: "AI-assisted second opinion on surface and crease findings, once it's ready",
    tier3Name: "Personalised pre-grading",
    tier3Body:
      "A card inspected by hand rather than by software alone, for when the automated pass isn't enough -- a high-value card, or a borderline one where the difference between two grades matters.",
    tier3Point1: "Everything in the standard report, plus a physical inspection",
    tier3Point2: "Written notes on the specific points a grader is likely to argue over",
    tier3Point3: "A frank view on whether the card is worth submitting at all",
    // Hand-off between the two brands' services pages. {businessName} is the
    // brand being pointed *at*, so an operator renaming either one renames it
    // in this copy too.
    crossToCareTitle: "Already own the card? {businessName} looks after it",
    crossToCareBody:
      "Analysis tells you whether a card is worth submitting. {businessName} is the other half: storage and handling advice, surface cleaning, honest restoration consultations, and packing a card properly for the journey.",
    crossToLabTitle: "Not sure it's worth grading yet? Start with {businessName}",
    crossToLabBody:
      "Before paying to have a card graded, {businessName} measures centering, corners, edges and surface, and tells you how the major companies are likely to treat it — so you find out before the fee, not after.",
    crossCta: "See {businessName} services",
    tier4Name: "Restorations",
    tier4Body:
      "Some problems can be improved; many cannot, and some attempts make things worse. The consultation is free precisely so nobody pays to be told no.",
    tier4Point1: "Free consultation before anything is agreed or attempted",
    tier4Point2: "An honest assessment of what can realistically be improved",
    tier4Point3: "The risks spelled out in writing, including the risk of damaging the card",
    tier4Warning:
      "Restoration carries real risk, and a restored card may be graded as altered or refused by a grading company. Nothing is attempted without discussing that with you first and agreeing it in writing.",
    tier5Name: "Pre-packaging for grading",
    tier5Body:
      "Cards prepared and packed properly for submission to a grading company, so a card doesn't pick up damage in transit that it didn't have when it left you.",
    tier5Point1: "Correct sleeving, card savers and protective packing",
    tier5Point2: "Submission paperwork prepared and checked",
    tier5Point3: "Per-card fee with discounts for bulk submissions",
    tier6Name: "Collection & shipping point",
    tier6Body:
      "A local drop-off point in Gibraltar for cards going to the grading companies, so you don't have to arrange international shipping and insurance for a single card yourself.",
    tier6Point1: "Drop off locally instead of shipping abroad",
    tier6Point2: "Cards grouped into bulk submissions to cut the cost per card",
    tier6Point3: "Tracked from handover to return",
  },
  howItWorks: {
    title: "How it works",
    subtitle: "From card to report in four steps.",
    step1Title: "Create a submission",
    step1Body:
      "Tell us the game and the card. It takes a moment, and it gives your card a reference code you can track.",
    step2Title: "Add a photo, or send the card",
    step2Body:
      "Upload a clear, flat photo of the front (and the back if you have it), or send the card in and we'll scan it properly. You'll confirm a rough crop so we know which card in the photo you mean; the exact edges are then found automatically, so the crop doesn't have to be perfect.",
    step3Title: "The analysis runs",
    step3Body:
      "Centering is measured from the border widths, corners and edges are checked for whitening and wear, and the surface is scanned for scratches and creases. It usually takes moments.",
    step4Title: "Read your report",
    step4Body:
      "You get a score per category, annotated images pinpointing each finding, and notes on how the major grading companies tend to treat them. Anything you think is wrong, you can dismiss -- the report then states clearly that it was adjusted.",
    faqTitle: "Common questions",
    faq1Q: "Is this an official grade?",
    faq1A:
      "No. It's an independent estimate to help you decide whether to submit. We're not affiliated with PSA, BGS, CGC, TAG, ACE or any other grading company, and we never predict a numeric grade on their behalf.",
    faq2Q: "How accurate is it?",
    faq2A:
      "Centering is measured and is the most reliable of the four. Corners and edges are good. Surface is the weakest: a flatbed scan uses diffuse light, while a grading company uses raking light that casts shadows along scratches, so faint surface defects can be missed and print texture can occasionally be flagged.",
    faq3Q: "Why did it flag something that isn't there?",
    faq3A:
      "Usually text or print texture read as a scratch. You can dismiss any finding you disagree with. Where the remaining findings still support a score, it updates immediately; where dismissing leaves nothing to measure from, the original measurement stands rather than jumping to a perfect score. The report then carries a clear notice that it was adjusted by you.",
    faq4Q: "What if the photo isn't perfect?",
    faq4A:
      "Photograph the card flat, straight on, filling most of the frame, in even light with no glare. You'll get a chance to adjust the crop before the analysis runs, and there's a snap-to-edge helper if your corners aren't quite right.",
    faq5Q: "What happens to my card if I send it in?",
    faq5A:
      "It's scanned and returned. Handling is kept to a minimum, and nothing is done to a physical card beyond scanning unless you've asked for it and agreed it in writing.",
    faq6Q: "What happens to my images?",
    faq6A:
      "They're stored so your report keeps working, and used for nothing else. You can delete a submission at any time, which removes its scans, analysis and report.",
    ctaTitle: "Ready to try it?",
    // No figure here: the allowance sentence is appended from /catalog/pricing
    // at render time, so this has to read properly on its own.
    ctaBody: "It's free to try.",
    methodologyLink: "Read the full methodology",
  },
  methodology: {
    title: "How the analysis works",
    subtitle:
      "What the software measures, how it decides, and where it gets things wrong. Every picture on this page is real output from the same code that reads your card.",

    demoTitle: "About the card in these pictures",
    demoBody:
      "The card below isn't a real one. It was built for this page and run through the actual analysis -- so the findings you see are genuine detector output, not a diagram of what we'd like it to do. We use a made-up card because a real card's artwork belongs to its publisher, and a customer's scan belongs to the customer.",

    prepTitle: "Before anything is measured",
    prepBody:
      "The card is found in the photo, straightened, and cropped to its own edges. A line is fitted along each of the four sides, using the straight parts and ignoring the corners, and the four corner points come from where those lines cross -- so a corner with a piece missing still has a known ideal tip to measure the loss against. The lines are placed to a fraction of a pixel, which matters because a whole pixel is already a meaningful share of the wear being measured. The crop you confirm tells us where to look, but it doesn't decide where the card's edges are; that comes from the card. Scale then comes from the card's real physical size, not from the image file. A phone photo's stored DPI has nothing to do with how many pixels cover the card, so we work from the fact that a standard card is 63mm by 88mm. That's why the report gives you millimetres you can check with a ruler.",

    centeringTitle: "Centering",
    centeringMeasures: "What it measures",
    centeringMeasuresBody:
      "The width of the printed border on all four sides, and how unevenly the card was cut.",
    centeringHow: "How",
    centeringHowBody:
      "The printed border's own colour is sampled just inside each cut, and then we look inward for where the colour stops matching it -- that's the inner edge of the border. Doing this at every position along a side, rather than on a handful of scan lines, gives a line that can be fitted rather than a single number. Two things come out of that fit. The border widths give the familiar left/right and top/bottom split. The *slope* gives something a single number per side cannot: whether the border runs parallel to the cut, or widens steadily along it. A card can be printed straight and trimmed crooked, and it then averages out to a perfect split while being visibly skewed -- graders penalise that separately, and so do we.",
    centeringWrong: "Where it goes wrong",
    centeringWrongBody:
      "A full-art card has no clean border to find, and the software says so rather than guessing: if too few positions along a side turn up a border, or what they turn up is not straight, centering is reported as not measurable instead of given a plausible-looking number. A holo card is the awkward middle case -- the pattern scatters the individual readings, so the border width is still measured from the side as a whole but the check for a crooked trim is not available, and the report says which of the two you got. The harder failure is quieter: a border found confidently in the wrong place, usually where print texture or glare crosses the colour step before the real edge does. That is why the lines are shown on your card and can be moved -- if one is visibly off, dragging it onto the real edge is faster than any amount of re-photographing.",
    centeringAlt:
      "The demonstration card with the printed border outlined, and each of the four border widths labelled in millimetres.",
    centeringCaption:
      "The four measurements, and the split they produce. This card was cut noticeably to one side.",

    cornersTitle: "Corners",
    cornersMeasures: "What it measures",
    cornersMeasuresBody:
      "How much card is missing from each of the four corners, in square millimetres, and how far each has frayed toward the white cardstock underneath.",
    cornersHow: "How",
    cornersHowBody:
      "Two separate measurements. For shape: the four corner points are worked out by extending the card's fitted edges until they cross, which gives the tip a perfect corner would have had, and anything missing inside that ideal corner is measured as an area. A card is die-cut to a rounded corner of about 1.5mm, so that much is expected and forgiven; what is left over is wear. For colour: the tip is compared against the same border a little further along the edge, in a colour space that separates how light something is from how colourful it is, because a frayed corner goes both lighter and less colourful. The worse of the two readings sets the corner's score, rather than the sum -- a chipped corner is nearly always a whitened one too, and a card should not be penalised twice for one piece of damage. The card's worst corner then carries half the weight of the whole category.",
    cornersWrong: "Where it goes wrong",
    cornersWrongBody:
      "The area measurement has a resolution limit. The card's outline is worked out to whole pixels, which at a typical photo works out to about a quarter of a square millimetre of uncertainty, so wear finer than roughly a half-millimetre nick is not reported at all -- we would rather miss it than invent it. The 1.5mm allowance for the factory cut is a standard figure rather than one measured from your specific card, so a card cut to a tighter or looser radius will read slightly worn or slightly generously. The colour half still struggles on a white or very pale border, where there is little colour to lose; the area half does not care what colour the border is, which is why those cards are no longer the blind spot they were. None of the thresholds come from any published grading standard.",
    cornersAlt:
      "A magnified top-left corner of the demonstration card, with the tip region and the reference region outlined, and the measured change in lightness and colour shown.",
    cornersCaption:
      "The tip against its reference. Lighter and less colourful means the corner has worn toward bare card; missing area is measured separately, against the corner point the card would have had.",

    edgesTitle: "Edges",
    edgesMeasures: "What it measures",
    edgesMeasuresBody:
      "Two things: whitening along each edge, and how straight the cut actually is, measured in millimetres.",
    edgesHow: "How",
    edgesHowBody:
      "For whitening: the printed border is located first, by looking inward from the cut until the colour changes, and only card from inside that border is used as the reference. This matters more than it sounds -- the reference used to sit at a fixed depth, and on a card whose border is narrower than that, it landed on the artwork instead. The comparison then measured the difference between a border and the art it frames, which is a design feature, not wear. A long unbroken run counts for more than the same amount scattered about, because that is how it is actually judged. For shape: a line is fitted along each cut and the distance the real edge wanders from it is recorded, so a nick is measured as a physical depth in millimetres rather than inferred from colour. The worse of the two readings sets the edge's score, not their sum -- a frayed edge is usually both, and it should not be penalised twice for one piece of damage.",
    edgesWrong: "Where it goes wrong",
    edgesWrongBody:
      "If the border is narrower than about a millimetre and a half, there is no clean card to compare against beside the cut, and that edge is judged on shape alone -- the report says so when it happens rather than guessing. The shape measurement describes the cut, so it cannot see wear that has discoloured the card without deforming it, and the colour measurement cannot see a bevelled or chewed edge that kept its colour; each covers the other's blind spot, which is why both are taken. Foil and holo texture near an edge can still register as either.",
    edgesAlt:
      "A magnified right edge of the demonstration card showing a white worn run inside the sampled edge strip, next to the reference strip taken from within the printed border.",
    edgesCaption:
      "The sampled strip and its reference, taken from inside the located border rather than at a fixed depth.",

    surfaceTitle: "Surface",
    surfaceMeasures: "What it measures",
    surfaceMeasuresBody: "Scratches, print lines and other marks across the face of the card.",
    surfaceHow: "How",
    surfaceHowBody:
      "The software slides a small window across the card and measures how much the image changes within it. Somewhere flat and clean barely changes; a scratch changes sharply. Anything well above the card's own average is flagged, then each flagged patch is measured: a real scratch is long and its stroke is thin, around six tenths of a millimetre. Printed text is roughly twice that thickness, and that difference is what lets the two be told apart.",
    surfaceWrong: "Where it goes wrong",
    surfaceWrongBody:
      "This is the weakest of the four, and we'd rather say so than have you find out. A flatbed scanner lights the card evenly from below; a professional grader uses a light held almost flat to the surface, which throws a shadow along a scratch and makes it obvious. We don't get that shadow, so faint scratches can be missed entirely -- and printed detail can be flagged when it shouldn't be.",
    surfaceRawAlt:
      "The demonstration card with everything the detector noticed highlighted in red: every line of body text, plus the scratch.",
    surfaceRawCaption:
      "Everything the first pass notices. All the printed text is in there -- to a contrast detector, a letter looks a lot like a scratch.",
    surfaceFilteredAlt:
      "The same card after filtering, with boxes around the scratch, the top edge of the art panel, and two words of body text.",
    surfaceFilteredCaption:
      "What survives the filter. The scratch is kept -- but so is the top edge of the art panel, and two words of text. Those last two are false positives, and they're why you can remove any finding you disagree with.",

    creasesTitle: "Creases",
    creasesMeasures: "What it measures",
    creasesMeasuresBody: "Long lines running across the card that ignore the printed design.",
    creasesHow: "How",
    creasesHowBody:
      "Contrast is boosted hard, then only long, roughly straight lines well inside the card's interior are kept -- the border is skipped, because printed frame edges are long straight lines too. Near-identical lines are merged so one crease isn't reported three times.",
    creasesWrong: "Where it goes wrong",
    creasesWrongBody:
      "A crease really wants angled light to cast a shadow along the ridge, and a flat scan doesn't provide it. So this one is deliberately advisory: a detected crease is shown to you but does not change any score. Foil and holo cards produce false positives here readily.",
    creasesAlt:
      "The demonstration card with two detected lines marked: the crease, and the top edge of the art panel.",
    creasesCaption:
      "Two lines found: the crease, and the top edge of the art panel -- which is printed, not damage. Exactly why creases don't move the score.",

    confidenceTitle: "How much to trust each number",
    confidenceBody:
      "They are not equally reliable, and treating them as if they were would be misleading.",
    confidence1: "Centering is measured, not estimated. Trust it, unless it's marked lower-confidence.",
    confidence2: "Corners and edges are good. They compare like with like on the same card.",
    confidence3:
      "Surface is the weakest, for the lighting reason above. Read the findings, look at the pictures, and use your own eyes.",
    confidence4:
      "Creases are advisory only and never affect a score.",

    adjustTitle: "When it's wrong, you decide",
    adjustBody:
      "Two things are yours to correct, and they work differently. Any finding can be dismissed: where the findings that remain still support a score it recalculates immediately, and where dismissing leaves nothing to measure from the original stands with your disagreement recorded beside it. Dismissing something says we got it wrong, which is not evidence the card is flawless, and it would be dishonest to award a perfect score on that basis. Centering also lets you move the border lines themselves. If the software put one in the wrong place you can drag it onto the real edge and the score is recalculated from where you put it -- a correction rather than an objection, which is why it does produce a new number. Movement is capped a few millimetres either side of where the border was detected, so a line can be fixed but not invented, and putting every line back where it started clears the adjustment completely. Either way the report states plainly, on every page, that you adjusted it and what changed. That mark cannot be turned off -- an adjusted report that looked identical to an unadjusted one would be worth nothing to whoever you show it to.",

    notTitle: "What this is not",
    notBody:
      "This is an independent estimate to help you decide whether a card is worth submitting. It is not a grade, and it never predicts a number on any grading company's behalf. We're not affiliated with {companies}, or with any other grading company. Their standards are their own, they change, and a human grader's judgement on the day is not something software can promise to reproduce.",

    ctaTitle: "See it on your own card",
    ctaBody: "It's free to try, and you can dismiss anything you disagree with.",
  },
  // The shared report at /r/{token}. Most people who read this page have never
  // seen the site and arrived from a link in a chat, so the framing has to
  // stand on its own -- everywhere else on the site, the visitor has at least
  // passed the landing page on the way in.
  publicReport: {
    metaDescription:
      "An independent pre-grade estimate: centering, corners, edges and surface, measured from photographs.",
    whatThisIsTitle: "What this is",
    whatThisIsBody:
      "An independent estimate of a card's condition, measured from photographs by automated image analysis. It is not a grade, and it does not predict one.",
    notAffiliated:
      "We are not a grading company and are not affiliated with {companies}, or with any other grading company.",
    checkedOn: "Checked on",
    scoresTitle: "What the analysis found",
    surfaceCaveat:
      "Surface is the least reliable of the four. These photographs are lit evenly rather than at an angle, so fine scratches can be missed and print texture is occasionally flagged as one.",
    adjustedTitle: "Adjusted by the card's owner",
    adjustedBody:
      "{count} auto-detected finding(s) were dismissed by whoever ran this check, and the scores reflect that rather than the unaltered analysis.",
    methodologyLink: "How the analysis works",
    ctaTitle: "Check your own card",
    ctaBody: "Upload a photo and get the same breakdown back. It's free to try.",
    ctaButton: "Start a free check",
    notFoundTitle: "This link isn't available",
    // Says nothing about which of the three reasons applies. A page that
    // distinguished "never existed" from "was revoked" would hand somebody
    // guessing tokens the one bit the 404 exists to withhold.
    notFoundBody:
      "It may have been turned off by the person who shared it, replaced with a new link, or never have existed. Ask them for a current one.",
  },
  contact: {
    title: "Get in touch",
    subtitle:
      "Questions about a card, a restoration, or anything on the services page -- ask away.",
    emailLabel: "Email",
    locationLabel: "Where we are",
    whatsappLabel: "WhatsApp",
    whatsappCta: "Message us on WhatsApp",
    responseLabel: "Response time",
    responseBody: "We usually reply within {days} working day(s).",
    inPersonLabel: "In person",
    inPersonBody:
      "Based in Gibraltar and happy to arrange a handover locally rather than posting a card. Get in touch and we'll sort out a time and place.",
    consultationTitle: "Restoration consultations are free",
    consultationBody:
      "If you're wondering whether something can be improved, ask before you try anything yourself. There's no charge for being told a card is best left alone.",
    noneTitle: "Contact details coming soon",
    noneBody: "Contact details haven't been published yet. Please check back shortly.",
    formTitle: "Send a message",
    formLede:
      "Prefer a form? Fill this in and it comes straight through. Questions about either side of the service are welcome.",
    nameLabel: "Your name",
    namePlaceholder: "What should we call you?",
    // No emailLabel here: the contact-details card above already defines one
    // and the form reuses it. A second copy is a duplicate key, which is a
    // compile error rather than an override.
    emailPlaceholder: "you@example.com",
    emailHelp: "So we can reply. It isn't used for anything else.",
    topicLabel: "What's it about?",
    topicLab: "{businessName} -- grading analysis",
    topicCare: "{businessName} -- card care",
    topicOther: "Something else",
    subjectLabel: "Subject",
    subjectPlaceholder: "A few words on what you need",
    codeLabel: "Submission code",
    codeOptional: "optional",
    codePlaceholder: "SUB-00001",
    codeHelp: "If your question is about a card you've already sent in.",
    messageLabel: "Your message",
    messagePlaceholder: "Tell us about the card, or ask anything you like.",
    submit: "Send message",
    sending: "Sending...",
    successTitle: "Message sent",
    successBody:
      "Thanks -- we've got it, and we'll reply to the address you gave. If it's urgent, WhatsApp is usually faster.",
    successAgain: "Send another",
    errorGeneric: "Something went wrong sending that. Please try again, or email us directly.",
    errorRequired: "Please fill this in.",
    errorEmail: "That doesn't look like an email address.",
    errorMessageShort: "Please write a little more so we can actually help.",
  },
  terms: {
    title: "Terms & Conditions",
    updated: "Last updated",
    updatedValue: "July 2026",
    intro:
      "These terms cover your use of {businessName}. By creating an account or submitting a card, you agree to them. Please read the disclaimer below in particular.",
    disclaimerTitle: "Important disclaimer",
    disclaimerBody:
      "{businessName} is an independent estimate. It is not affiliated with, endorsed by, or a guarantee of the outcome from PSA, Beckett Grading Services (BGS), CGC, TAG, ACE, or any other third-party grading company. Nothing we produce is a grade, a prediction of a grade, or a promise about what any grading company will decide. A card that scores well here may still grade lower than you expect, and vice versa.",
    s1Title: "1. What this service does",
    s1Body:
      "We analyse images of your trading cards and produce a report covering centering, corners, edges and surface, together with notes on the points of contention that could affect how different grading companies treat the card. The report is informational and is intended to help you decide whether to pay for a real grading submission.",
    s2Title: "2. What this service does not do",
    s2Body:
      "We do not grade cards, issue grades, or act on behalf of any grading company. We do not guarantee that a card will receive any particular grade, that it will be accepted for grading, or that it will increase in value. We are not a valuation service and our reports are not an appraisal.",
    s3Title: "3. Accuracy and known limitations",
    s3Body:
      "Automated image analysis has real limits and we would rather state them than bury them. Scans use diffuse light rather than the raking light a grading company uses, so faint surface scratches and creases can be missed. Printed text and holographic patterns can occasionally be flagged as defects. Measurement accuracy depends on the quality and framing of the image you provide. Findings marked lower-confidence are exactly that. You should treat the report as one input among several, not as a decision on its own.",
    s4Title: "4. Reports you have adjusted",
    s4Body:
      "You can dismiss individual findings you believe are incorrect. Where the findings that remain still support a score, it updates to reflect that; where dismissing leaves nothing to measure from, the original measurement stands. Any report where you have done so is labelled as client-adjusted, and both the original and adjusted scores are shown. You are responsible for adjustments you make, and an adjusted report should not be presented to anyone else as an unmodified assessment.",
    s5Title: "5. Your account",
    s5Body:
      "You must give an accurate email address and keep your password secure. You are responsible for activity under your account. Do not upload images you do not have the right to use, and do not upload anything unlawful. We may suspend or close an account that is being misused.",
    s6Title: "6. Physical cards",
    s6Body:
      "Where you send a card to us, we handle it with care and keep handling to a minimum. Nothing is done to a physical card beyond scanning unless you have specifically requested it and we have agreed it with you in writing. You are responsible for postage to us and for insuring a card in transit at a value you are comfortable with. Restoration work, where agreed, carries an inherent risk of damage and a restored card may be graded as altered or refused outright by a grading company; that risk is explained and agreed before any work begins.",
    s7Title: "7. Fees",
    s7Body:
      "The basic image analysis is currently free to use, subject to fair-use limits. Paid services are described on the Services page; where a service is marked as coming soon or planned it is not yet available to buy. Fees for any paid service are agreed with you before work starts.",
    s8Title: "8. Limitation of liability",
    s8Body:
      "To the extent permitted by law, we are not liable for decisions you make on the basis of a report, for grading outcomes, for loss of profit or expected value, or for the difference between a report and a grading company's decision. Nothing in these terms limits liability for death or personal injury caused by negligence, for fraud, or for anything else that cannot lawfully be limited. Where a card is lost or damaged while in our care, our liability is limited to the agreed handling arrangements for that card.",
    s9Title: "9. Changes",
    s9Body:
      "We may update these terms as the service develops. The date at the top of this page shows when they last changed, and continuing to use the service after a change means you accept the updated terms.",
    s10Title: "10. Governing law",
    s10Body:
      "These terms are governed by the law of Gibraltar, and disputes fall to the courts of Gibraltar.",
    s11Title: "11. Contact",
    s11Body: "Questions about these terms can be sent to us via the contact page.",
    reviewNote:
      "These terms are provided in good faith and in plain language. They are not legal advice; if you need advice about your own position, speak to a qualified adviser.",
  },
  privacy: {
    title: "Privacy Policy",
    updated: "Last updated",
    updatedValue: "July 2026",
    intro:
      "This explains what personal data {businessName} collects, why, and what you can do about it. We collect as little as the service needs to work.",
    s1Title: "1. Who is responsible",
    s1Body:
      "{businessName}, based in Gibraltar, is the data controller for the personal data described here. You can reach us via the contact page.",
    s2Title: "2. What we collect",
    s2Body:
      "Your email address and a securely hashed password, so you can log in. Details of the cards you submit -- game, card name, set and number. The images you upload or that we produce by scanning your card, along with the analysis derived from them. Basic records of actions taken on your submissions, so there is an audit trail. We do not collect payment card details on this site, and we do not use advertising or tracking cookies.",
    s3Title: "3. Why we use it, and on what basis",
    s3Body:
      "We use your email to run your account, verify it, and send you notifications about your own submissions. We use your card details and images to produce the analysis and report you asked for. Both are necessary to perform the service you requested. We keep audit records to protect the integrity of the service, which is our legitimate interest as an operator.",
    s4Title: "4. Your card images",
    s4Body:
      "Images you upload are used to produce your report and for nothing else. They are not sold, not published, and not used to advertise the service or to train anything without asking you first and separately. They are stored so your report continues to work when you open it later.",
    s5Title: "5. How long we keep it",
    s5Body:
      "Submissions, scans, analysis and reports are kept while your account is open, so you can go back to them. Deleting a submission removes its scans, analysis and report permanently and immediately. Ask us to close your account and we will delete your personal data, keeping only what we are legally required to retain.",
    s6Title: "6. Who else sees it",
    s6Body:
      "Nobody, other than the service operator. We do not sell personal data and we do not share it with grading companies or any other third party, except where a supplier is strictly necessary to run the service (such as hosting or sending email), or where we are legally required to disclose it.",
    s7Title: "7. Your rights",
    s7Body:
      "Under Gibraltar data protection law you can ask for a copy of your data, ask us to correct it, ask us to delete it, object to or ask us to restrict certain processing, and ask for your data in a portable form. Contact us and we will respond within the statutory time limit. If you are unhappy with how we handle a request, you can complain to the Gibraltar Regulatory Authority.",
    s8Title: "8. Security",
    s8Body:
      "Passwords are stored hashed, never in plain text. Access to submissions and images is restricted to the account that owns them and to the operator. No system is perfectly secure, but we keep access narrow and the stored data minimal.",
    s9Title: "9. Changes",
    s9Body:
      "If this policy changes, the date at the top of this page changes with it. Material changes affecting how we use your data will be brought to your attention.",
    reviewNote:
      "This policy is written in plain language rather than legal boilerplate. It is not legal advice; if you need advice about your own position, speak to a qualified adviser.",
  },
} as const;

type Widen<T> = { [K in keyof T]: T[K] extends string ? string : Widen<T[K]> };

export type Dictionary = Widen<typeof en>;
