export const VOICE_CATEGORIES = [
  { value: 'any', label: 'Neutral / Any' },
  { value: 'feminine', label: 'Feminine' },
  { value: 'masculine', label: 'Masculine' },
]

export function assignCharacterVoices(characters, categories = {}) {
  const counts = { any: 0, feminine: 0, masculine: 0 }
  // Include the actor: selecting a different role must not shift these slots.
  return Object.fromEntries(characters.map((character) => {
    const selected = categories[character]
    const category = VOICE_CATEGORIES.some(({ value }) => value === selected) ? selected : 'any'
    return [character, { voice_category: category, voice_index: counts[category]++ }]
  }))
}

export function voicePlaybackKey(actor, assignments) {
  // Remounting the player releases its entire cache when its audio inputs change.
  return JSON.stringify([actor, assignments])
}
