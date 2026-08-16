<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Two rules the site is held to, and how to check them

Both were established by measuring, after a pass that tested only what looked likely. Measure rather
than eyeball: the browser can answer both questions exactly.

**No page scrolls horizontally.** Check `document.body.scrollWidth === window.innerWidth` at **320,
375, 768 and 1280**, signed in *and* signed out, in **both languages**. Every one of those has caught
something the others did not, and **768 is still broken** — signed in, and signed out in Spanish
too, where the longer nav labels tip it to 777 (see the root `AGENTS.md`). Both halves of the rule
earned their place on that one width: the first sweep tested 320, 375 and 1280 and missed it, and a
later English-only pass at 768 missed the signed-out case for the same reason.

The header is the usual culprit, and the fix has a shape worth knowing. Both brand names come from
`Settings`, so the brand switch's width is operator-controlled and unbounded; `min-w-0` plus
`truncate` lets it be the element that gives, and `md:min-w-max` puts the floor back once the desktop
nav appears, because there the nav is the wide one and letting the brand group shrink clipped the
brand name. Wide content — tables especially — scrolls inside its own `overflow-x-auto` container,
never the page.

**No interactive control is under 24×24 px** (WCAG 2.5.8). Enumerate `a, button, [role=slider]`,
take `getBoundingClientRect()`, and assert. Raw `input` elements read 0×0 or 13×13 because they sit
behind a styled label — measure the visible control, not the input.

Drag handles get a **44px transparent hit area around an unchanged dot**, sized that way round on
purpose: the dot marks where the border line or card corner sits, so growing it would obscure the
measurement it exists to let you check. For text and icon controls, negative margins absorb the new
padding so no layout moves (`-my-2 py-2`).

## Copy lives in `lib/i18n/`, and the numbers do not

`Dictionary = Widen<typeof en>` makes a missing Spanish key a **type error**, so `npx tsc --noEmit`
is the translation-completeness check.

Prices and allowances are never written into the copy — they come from `/catalog/pricing`, so an
operator changing a figure in the admin panel changes the page. Copy carries `{price}` / `{count}`
placeholders instead.

**Outside `/pricing`, a quoted figure is appended to a sentence that already stands without it.**
The marketing CTAs on `/how-it-works` and `/methodology` read "It's free to try", and
`useFreeAllowanceSentence` adds "Free accounts get 3 checks every 7 days." once the catalog answers.
An unreachable API therefore costs precision rather than leaving a hole in the page. `/pricing`
itself is the deliberate exception and shows a `Skeleton`, because a price list with a price missing
from it is not a price list — but a call to action with a number missing is still a call to action.

Those two CTAs were the last copy in the site carrying a figure of its own, and they said "The first
check is free" while the seed granted three a week. Nothing catches this automatically: a test
banning digits in the copy would trip over `physicalTurnaround`'s honest "5-7 working days", and the
placeholder forms contain no digit to key off. Grep the dictionaries for a number before adding one.

**Read Spanish back rendered in a browser, not just typechecked.** Accented characters and em dashes
have been mangled more than once by tooling that round-trips the file; `tsc` cannot see it and the
page can. So can a formatter that is not given a locale: `Intl.ListFormat` and
`Date.toLocaleDateString` both default to the **browser's** locale rather than the app's, which put
"PSA, BGS, CGC, TAG and ACE" in the middle of a Spanish sentence on the shared-report page. Pass
`locale` from `useLocale()` explicitly every time — `useGradingCompanies` already does, and it is
the only reason the same bug is not on the landing page.

## The shared report at `/r/[token]` is a server component, and has to stay one

Two things depend on it, and both are silent when they break.

`generateMetadata` is server-only, and the link preview is the point of the feature — a
client-rendered page unfurls in Discord as a blank card. And an ISR page is served
`s-maxage=60, stale-while-revalidate=...` while a **dynamic** one gets
`private, no-cache, no-store`, which would put every view of a viral link onto a home server running
OpenCV.

Getting ISR needs more than `export const revalidate`. A dynamic segment with no
`generateStaticParams` renders on demand and is *not* cached, so the route also exports one
returning an **empty array** — the documented requirement, see
`node_modules/next/dist/docs/01-app/03-api-reference/04-functions/generate-static-params.md`. The
build output is how to check: `●` is right, `ƒ` means the caching is gone. The first version of this
route built as `ƒ` with `revalidate = 60` set and looking correct, which is how quietly it goes.

Confirm the header itself in a **production** build; `next dev` will not show it.

**An `<img>` that ships in server HTML may never fire `onLoad`.** The browser can finish loading it
before hydration attaches the handler, so any state set only in `onLoad` stays null forever. That
hid the centering remap on `/r/[token]`: the frame fell back to the detected box, on a warm cache
only, which is the worst way for that particular bug to behave. Pair `onLoad` with a mount effect
checking `ref.current.complete && naturalWidth > 0`. `AnnotatedPhoto` does not need this because its
src is a blob URL assigned after a fetch, so the load always happens under React — do not read its
lack of the guard as evidence the guard is unnecessary.
