import type { Variants } from "framer-motion";

/** Standard page lift-in — spread onto a motion.div wrapping each page. */
export const pageTransition = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.25, ease: "easeOut" },
} as const;

/** Stagger container for animated lists. `stagger` is the gap between children
 * in seconds (30ms = 0.03, 50ms = 0.05). */
export function staggerContainer(stagger = 0.03): Variants {
  return {
    hidden: {},
    show: { transition: { staggerChildren: stagger } },
  };
}

/** List item that fades up — for vertical lists (rows, conversations, chunks). */
export const itemFadeUp: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2, ease: "easeOut" } },
};

/** List item that fades in from the left — for the left-to-right stat row. */
export const itemFadeLeft: Variants = {
  hidden: { opacity: 0, x: -8 },
  show: { opacity: 1, x: 0, transition: { duration: 0.2, ease: "easeOut" } },
};
