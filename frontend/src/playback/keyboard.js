export function handlePlayerSpace(event, player, active, advance) {
  if (!active || event.code !== 'Space' || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
  const target = event.target
  if (!target || typeof target.closest !== 'function') return
  // Preserve native controls (including Space activation of buttons) everywhere.
  if (target.closest('button, input, select, textarea, a, [contenteditable], [role="textbox"]')) return
  if (!player?.contains(target) && target.tagName !== 'BODY' && target.tagName !== 'HTML') return
  // Own Space even while loading/playing, and suppress scrolling on key repeats.
  event.preventDefault()
  if (!event.repeat) advance()
}
