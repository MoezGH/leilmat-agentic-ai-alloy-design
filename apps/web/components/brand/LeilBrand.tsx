/**
 * The Leil mark, as LeilCFD and LeilFEA wear it: "LEIL-MAT" in the brand's headline face (Barlow Condensed Black,
 * uppercase), the hyphen and the tool's name part of the one wordmark, with the INFINITE bloom to its left as the symbol.
 * "Leil" is the product's name and stays as it is.
 */
import Link from "next/link";

import { Bloom } from "@/components/brand/Bloom";

export function LeilBrand({ tool = "MAT", subtitle, href = "/" }: {
  /** The Leil tool, set after "LEIL-" ("MAT" → LEIL-MAT). */
  tool?: string;
  /** A short descriptor after the logo, from lg up. */
  subtitle?: string;
  href?: string;
}) {
  return (
    <Link href={href} aria-label={`Leil ${tool} home`} className="flex shrink-0 items-center gap-2 sm:gap-2.5">
      {/* The bloom, the symbol to the left of the wordmark (32 px and up: smaller, the seeds blur together). */}
      <Bloom decorative size={32} className="shrink-0 self-center" />
      {/* One word: it never breaks at its hyphen. */}
      <span className="headline whitespace-nowrap text-[22px] text-fg sm:text-[24px]">Leil-{tool}</span>
      {subtitle && <span className="label hidden truncate text-[10px] text-subtle lg:inline">{subtitle}</span>}
    </Link>
  );
}
