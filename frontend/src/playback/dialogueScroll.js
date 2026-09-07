// Place the start of a turn near the upper third, leaving previous context.
// Clamp at either end; long speeches remain fully available for manual scrolling.
export function dialogueScrollTop(lineTop, viewportHeight, contentHeight) {
  return Math.max(0, Math.min(lineTop - viewportHeight / 3, contentHeight - viewportHeight))
}
