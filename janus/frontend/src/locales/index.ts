import en from './en'
import pt, { type Dictionary } from './pt'
import es from './es'

export type Locale = 'pt' | 'en' | 'es'

export const LOCALES: Locale[] = ['pt', 'en', 'es']

export const dictionaries: Record<Locale, Dictionary> = { pt, en, es }

export type { Dictionary }
