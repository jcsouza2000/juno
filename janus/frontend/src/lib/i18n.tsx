'use client'

// Camada i18n leve via React Context — sem dependência externa nem reestruturação
// de rotas. O idioma é persistido em localStorage (mesmo padrão de useActiveCompany)
// e sincronizado entre abas. Use `const { t, locale, setLocale } = useI18n()`.

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { dictionaries, LOCALES, type Locale } from '@/locales'

const STORAGE_KEY = 'juno_locale'
const CHANGE_EVENT = 'juno-locale-changed'

type Vars = Record<string, string | number>

interface I18nValue {
  locale: Locale
  setLocale: (l: Locale) => void
  t: (key: string, vars?: Vars) => string
}

const I18nContext = createContext<I18nValue | null>(null)

function resolve(dict: object, key: string): string | undefined {
  let current: unknown = dict
  for (const part of key.split('.')) {
    if (current && typeof current === 'object' && part in current) {
      current = (current as Record<string, unknown>)[part]
    } else {
      return undefined
    }
  }
  return typeof current === 'string' ? current : undefined
}

function interpolate(text: string, vars?: Vars): string {
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (match, name) =>
    name in vars ? String(vars[name]) : match,
  )
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('pt')

  useEffect(() => {
    const load = () => {
      const saved = window.localStorage.getItem(STORAGE_KEY)
      if (saved && (LOCALES as string[]).includes(saved)) {
        setLocaleState(saved as Locale)
        document.documentElement.lang = saved
      }
    }
    load()
    window.addEventListener(CHANGE_EVENT, load)
    window.addEventListener('storage', load)
    return () => {
      window.removeEventListener(CHANGE_EVENT, load)
      window.removeEventListener('storage', load)
    }
  }, [])

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l)
    window.localStorage.setItem(STORAGE_KEY, l)
    document.documentElement.lang = l
    window.dispatchEvent(new Event(CHANGE_EVENT))
  }, [])

  const t = useCallback(
    (key: string, vars?: Vars): string => {
      const value = resolve(dictionaries[locale], key) ?? resolve(dictionaries.pt, key) ?? key
      return interpolate(value, vars)
    },
    [locale],
  )

  return <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n deve ser usado dentro de <I18nProvider>')
  return ctx
}
