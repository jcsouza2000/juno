"use client"

import { signOut, useSession } from "next-auth/react"
import { useActiveCompany } from "@/lib/tenant"
import { useI18n } from "@/lib/i18n"
import { LOCALES, type Locale } from "@/locales"

function initials(name?: string | null, email?: string | null) {
  const source = name || email || "JUNO"
  return source
    .split(/\s|@/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("")
}

export default function Header() {
  const { data: session } = useSession()
  const { company } = useActiveCompany()
  const { t, locale, setLocale } = useI18n()
  const user = session?.user

  return (
    <header className="bg-white border-b border-gray-100 h-16 flex items-center justify-between px-8 ml-64">
      <div>
        <h2 className="text-lg font-semibold text-gray-800">{t("header.title")} v0.3.2</h2>
      </div>
      <div className="flex items-center gap-4">
        {/* Seletor de idioma */}
        <select
          value={locale}
          onChange={(e) => setLocale(e.target.value as Locale)}
          aria-label={t("lang.select")}
          className="text-xs font-bold uppercase border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600 hover:border-[#0A2342] focus:outline-none focus:border-[#0A2342] cursor-pointer bg-white"
        >
          {LOCALES.map((l) => (
            <option key={l} value={l}>
              {l.toUpperCase()}
            </option>
          ))}
        </select>
        <span className="px-3 py-1 rounded-full bg-[#C9A959]/10 text-[#8A6D1D] text-xs font-bold uppercase">
          {company ? company.name : t("header.hybridSaas")}
        </span>
        <div className="text-right">
          <p className="text-sm font-semibold text-gray-800">{user?.name || user?.email || t("header.user")}</p>
          <p className="text-xs text-gray-500 uppercase">{user?.role || t("header.noProfile")}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-[#0A2342] text-white flex items-center justify-center text-xs font-bold">
          {initials(user?.name, user?.email)}
        </div>
        <button
          type="button"
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="text-xs font-semibold text-gray-500 hover:text-[#0A2342]"
        >
          {t("header.signOut")}
        </button>
      </div>
    </header>
  );
}
