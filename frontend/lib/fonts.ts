import { Titan_One } from "next/font/google";

// Scoped to the header/site-name text only (see NavBar.tsx) -- not applied
// to <body>, so the rest of the app keeps the plain --font-sans stack.
export const titanOne = Titan_One({
  weight: "400",
  subsets: ["latin"],
  display: "swap",
});
