export const MAX_FILE_SIZE = 10 * 1024 * 1024
export const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp']

export function validateFile(f) {
  if (!ALLOWED_TYPES.includes(f.type)) return '不支援的檔案類型。允許：PNG、JPEG、WebP。'
  if (f.size > MAX_FILE_SIZE) return '檔案過大，最大允許 10 MB。'
  return null
}
