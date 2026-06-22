/**
 * ErrorNote — the one-line red error message shown in a cloud card's
 * result slot when a job fails (Tier C component kit).  Extracted from
 * four byte-identical copies across the cloud cards.
 */
export function ErrorNote({ message }: { message: string }) {
  return <p className="text-[9px] text-rose-400 font-mono leading-snug">{message}</p>;
}
