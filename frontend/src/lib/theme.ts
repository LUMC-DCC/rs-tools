export const THEME_STORAGE_KEY = 'rs-tools-theme'

export type ThemePreference = 'auto' | 'light' | 'dark'
export type ResolvedTheme = Exclude<ThemePreference, 'auto'>

const isThemePreference = (value: string | null): value is ThemePreference =>
  value === 'auto' || value === 'light' || value === 'dark'

export function readThemePreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    return isThemePreference(stored) ? stored : 'auto'
  } catch {
    return 'auto'
  }
}

export function resolveTheme(preference: ThemePreference, prefersDark: boolean): ResolvedTheme {
  return preference === 'auto' ? (prefersDark ? 'dark' : 'light') : preference
}

export function applyThemePreference(preference: ThemePreference): ResolvedTheme {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const resolved = resolveTheme(preference, prefersDark)
  const root = document.documentElement
  root.dataset.theme = resolved
  root.dataset.themePreference = preference
  root.style.colorScheme = resolved

  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', resolved === 'dark' ? '#0b0c10' : '#f7f9fb')

  return resolved
}

export function storeThemePreference(preference: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference)
  } catch {
    // The selected theme still applies for this page when storage is unavailable.
  }
}
