/**
 * Composable to build complete URLs for assets
 * Handles both relative and absolute paths
 * Uses VITE_SITE_URL from environment variables
 */

export function useAssetUrl() {
  const siteUrl = import.meta.env.VITE_SITE_URL || 'http://localhost'

  /**
   * Build a complete URL for an asset
   * @param path - Asset path (can be relative like /media/... or absolute like http://...)
   * @returns Complete URL
   */
  function buildAssetUrl(path: string | null | undefined): string {
    if (!path) return ''

    // If already an absolute URL, return as is
    if (path.startsWith('http://') || path.startsWith('https://')) {
      return path
    }

    // If relative path, prepend site URL
    if (path.startsWith('/')) {
      return `${siteUrl}${path}`
    }

    // If no leading slash, prepend site URL with slash
    return `${siteUrl}/${path}`
  }

  return {
    buildAssetUrl,
    siteUrl
  }
}
