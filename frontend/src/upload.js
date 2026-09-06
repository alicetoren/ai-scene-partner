// Early feedback only; the backend remains authoritative about content and size.
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024

export function validateScriptFile(file) {
  if (!file) return 'Choose a TXT or PDF script before analyzing.'
  if (!/\.(txt|pdf)$/i.test(file.name)) return 'Choose a TXT (.txt) or PDF (.pdf) script.'
  if (file.size > MAX_UPLOAD_BYTES) return 'The script is too large. Upload a file of 10 MiB or less.'
  if (file.size === 0) return 'The selected file is empty.'
  return ''
}
