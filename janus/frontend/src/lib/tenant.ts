"use client"

import { useEffect, useState } from "react"
import { useSession } from "next-auth/react"

type TenantCompany = {
  id: number
  name: string
}

const ACTIVE_COMPANY_KEY = "juno_active_company"
const ACTIVE_COMPANY_EVENT = "juno-active-company-changed"

export function setActiveCompany(company: TenantCompany) {
  window.localStorage.setItem(ACTIVE_COMPANY_KEY, JSON.stringify(company))
  window.dispatchEvent(new Event(ACTIVE_COMPANY_EVENT))
}

export function useActiveCompany() {
  const { data: session, status } = useSession()
  const [selectedCompany, setSelectedCompany] = useState<TenantCompany | null>(null)

  useEffect(() => {
    const loadSelectedCompany = () => {
      try {
        const raw = window.localStorage.getItem(ACTIVE_COMPANY_KEY)
        setSelectedCompany(raw ? JSON.parse(raw) : null)
      } catch {
        setSelectedCompany(null)
      }
    }

    loadSelectedCompany()
    window.addEventListener(ACTIVE_COMPANY_EVENT, loadSelectedCompany)
    window.addEventListener("storage", loadSelectedCompany)
    return () => {
      window.removeEventListener(ACTIVE_COMPANY_EVENT, loadSelectedCompany)
      window.removeEventListener("storage", loadSelectedCompany)
    }
  }, [])

  const sessionCompany = session?.user?.companies?.[0] ?? null
  const devCompanyId =
    process.env.NODE_ENV !== "production"
      ? Number(process.env.NEXT_PUBLIC_DEV_COMPANY_ID || 1)
      : null
  const devCompany =
    !sessionCompany && status !== "loading" && devCompanyId
      ? { id: devCompanyId, name: "JUNO Dev Tenant" }
      : null
  const company = selectedCompany ?? sessionCompany ?? devCompany

  return {
    company,
    companyId: company?.id ?? null,
    isLoading: status === "loading",
  }
}
