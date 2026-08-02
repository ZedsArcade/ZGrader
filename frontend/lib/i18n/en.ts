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
  cropAdjust: {
    title: "Confirm the card's corners",
    instructions: "Drag the 4 handles onto the exact corners of the card, then confirm.",
    confirmButton: "Confirm crop",
    confirming: "Confirming…",
    loadFailed: "Couldn't load the photo for cropping.",
    confirmFailed: "Couldn't confirm the crop.",
    snapButton: "Snap to detected edges",
    snapFailed: "Couldn't refine the crop.",
    rotateLeft: "Rotate left",
    rotateRight: "Rotate right",
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
    lede: "A local collector trying to make caring for cards less of a guessing game.",
    body1:
      "{businessName} started in Gibraltar, run by someone who collects the same things you do. Anyone who has sent a card away for grading knows the feeling: you pay the fee, you post something you care about, you wait weeks, and only then do you find out whether it was worth doing at all.",
    body2:
      "That gap is what this service exists to close. Before you commit to a submission, you get a measured look at centering, corners, edges and surface, with annotated images showing exactly what was picked up and why. If the card isn't going to grade the way you hoped, far better to learn that here than after paying for a real submission.",
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
    warningTitle: "Read this before asking for restoration",
    warningBody:
      "Restoration carries real risk. A restored card may be graded as altered, or refused outright, by a grading company -- and that outcome is permanent. Nothing is attempted without discussing it with you first and agreeing it in writing. If the honest answer is to leave a card alone, that is the answer you will get.",
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
      "Upload a clear, flat photo of the front (and the back if you have it), or send the card in and we'll scan it properly. You'll confirm the crop so the measurements are taken from the card itself, not the background.",
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
      "Usually text or print texture read as a scratch, or a crop that clipped into the card. You can dismiss any finding you disagree with. Where the remaining findings still support a score, it updates immediately; where dismissing leaves nothing to measure from, the original measurement stands rather than jumping to a perfect score. The report then carries a clear notice that it was adjusted by you.",
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
    ctaBody: "The first check is free.",
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
      "The card is found in the photo, straightened, and cropped to its own edges -- you confirm that crop yourself, because every measurement afterwards is taken from it. Scale then comes from the card's real physical size, not from the image file. A phone photo's stored DPI has nothing to do with how many pixels cover the card, so we work from the fact that a standard card is 63mm by 88mm. That's why the report gives you millimetres you can check with a ruler.",

    centeringTitle: "Centering",
    centeringMeasures: "What it measures",
    centeringMeasuresBody:
      "The width of the printed border on all four sides, and how unevenly the card was cut.",
    centeringHow: "How",
    centeringHowBody:
      "Twenty sample lines are scanned inward from each cut edge, looking for the sharpest jump in brightness -- the boundary where the border meets the card's edge. The middle value of those twenty is taken, so one odd line can't skew the result. The four widths become a left/right and top/bottom split.",
    centeringWrong: "Where it goes wrong",
    centeringWrongBody:
      "A full-art or holo card has no clean border to find. The software notices this rather than guessing: if the twenty sample lines disagree with each other, the reading is marked lower-confidence and flagged as such in your report.",
    centeringAlt:
      "The demonstration card with the printed border outlined, and each of the four border widths labelled in millimetres.",
    centeringCaption:
      "The four measurements, and the split they produce. This card was cut noticeably to one side.",

    cornersTitle: "Corners",
    cornersMeasures: "What it measures",
    cornersMeasuresBody: "Whitening at each of the four corners.",
    cornersHow: "How",
    cornersHowBody:
      "A worn corner frays toward the white cardstock underneath, so colour intensity drops off at the tip. Each corner is compared against a reference patch a little further in on the same card -- the difference is the wear.",
    cornersWrong: "Where it goes wrong",
    cornersWrongBody:
      "This measures discolouration, not shape. A corner that has been rounded or knocked flat without changing colour is not caught here, and we would rather tell you that than quietly score it as clean -- measuring missing material properly is work still to come. The thresholds are tuned from real scans rather than taken from any published standard, and because the signal is a loss of colour, a corner whose artwork is naturally pale reads as slightly worn while a white border can hide genuine whitening altogether.",
    cornersAlt:
      "A magnified top-left corner of the demonstration card, with the tip region and the reference region outlined, and their colour intensity values shown.",
    cornersCaption:
      "The tip against its reference. A big drop means the corner has worn toward bare card.",

    edgesTitle: "Edges",
    edgesMeasures: "What it measures",
    edgesMeasuresBody:
      "Whitening along each edge, and whether it runs continuously or is just a speck.",
    edgesHow: "How",
    edgesHowBody:
      "A thin strip along each edge is compared with a reference strip immediately inside it. The reference is deliberately local: plenty of cards have a border that differs from the artwork in the middle, and comparing an edge against the centre of the card would flag every one of them. A long unbroken run of whitening counts for more than the same amount scattered about, because that's how it's actually judged.",
    edgesWrong: "Where it goes wrong",
    edgesWrongBody:
      "On a card with an unusually narrow border, the reference strip can land on the artwork instead of the border, and the comparison then measures a design change rather than wear.",
    edgesAlt:
      "A magnified right edge of the demonstration card showing a white worn run inside the sampled edge strip, next to its reference strip.",
    edgesCaption: "The sampled strip, its reference, and the whitened run between them.",

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
      "Every finding can be dismissed. Where the findings that remain still support a score, it recalculates immediately. Where dismissing leaves nothing to measure from -- centering has only one finding, so dismissing it removes the whole basis for the number -- the original measurement stands and your disagreement is recorded alongside it. Dismissing something is a statement that we got it wrong, which is not the same as evidence the card is flawless, and it would be dishonest to award a perfect score on that basis. Either way the report states plainly, on every page, that it was adjusted by you and which findings were removed. That mark can't be turned off -- an adjusted report that looked identical to an unadjusted one would be worth nothing to whoever you show it to.",

    notTitle: "What this is not",
    notBody:
      "This is an independent estimate to help you decide whether a card is worth submitting. It is not a grade, and it never predicts a number on any grading company's behalf. We're not affiliated with {companies}, or with any other grading company. Their standards are their own, they change, and a human grader's judgement on the day is not something software can promise to reproduce.",

    ctaTitle: "See it on your own card",
    ctaBody: "The first check is free, and you can dismiss anything you disagree with.",
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
