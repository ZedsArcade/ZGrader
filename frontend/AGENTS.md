<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Two rules the site is held to, and how to check them

Both were established by measuring, after a pass that tested only what looked likely. Measure rather
than eyeball: the browser can answer both questions exactly.

**No page scrolls horizontally.** Check `document.body.scrollWidth === window.innerWidth` at **320,
375, 768 and 1280**, signed in *and* signed out, in **both languages**. Every one of those has caught
something the others did not — 768 signed in is still broken (see the root `AGENTS.md`), and it was
missed precisely because the first sweep tested 320, 375 and 1280.

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

**Read Spanish back rendered in a browser, not just typechecked.** Accented characters and em dashes
have been mangled more than once by tooling that round-trips the file; `tsc` cannot see it and the
page can.
