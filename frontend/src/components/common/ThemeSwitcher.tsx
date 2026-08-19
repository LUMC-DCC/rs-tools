import { Moon, Sun, SunMoon } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  applyThemePreference,
  readThemePreference,
  storeThemePreference,
  type ThemePreference,
} from '../../lib/theme'

const THEME_OPTIONS = {
  auto: { next: 'light', label: 'Switch to light mode', Icon: SunMoon },
  light: { next: 'dark', label: 'Switch to dark mode', Icon: Sun },
  dark: { next: 'auto', label: 'Switch to system preference', Icon: Moon },
} satisfies Record<
  ThemePreference,
  { next: ThemePreference; label: string; Icon: typeof SunMoon }
>

export default function ThemeSwitcher() {
  const [preference, setPreference] = useState<ThemePreference>(readThemePreference)

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => applyThemePreference(preference)
    apply()
    if (preference === 'auto') media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [preference])

  const selectTheme = (next: ThemePreference) => {
    storeThemePreference(next)
    setPreference(next)
  }

  const { next, label, Icon } = THEME_OPTIONS[preference]

  return (
    <button
      type="button"
      className="theme-switcher"
      aria-label={label}
      title={label}
      onClick={() => selectTheme(next)}
    >
      <Icon size={18} aria-hidden="true" />
    </button>
  )
}
