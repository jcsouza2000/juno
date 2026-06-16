"use client"

import { useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import { api } from "@/lib/api"

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
  const [fetchedCompany, setFetchedCompany] = useState<TenantCompany | null>(null)

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

  // Sem empresa na sessao nem selecionada: busca as empresas reais do backend.
  // O backend resolve o usuario autenticado (token da sessao) ou, em dev com
  // JUNO_DEV_AUTH_BYPASS, o dev-user com suas empresas reais (ex.: Agora SA).
  // Isso substitui o antigo fallback hardcoded (que mostrava nome errado e era
  // desligado em build de producao).
  useEffect(() => {
    if (status === "loading") return
    if (selectedCompany || sessionCompany || fetchedCompany) return

    let active = true
    const devId = process.env.NEXT_PUBLIC_DEV_COMPANY_ID
      ? Number(process.env.NEXT_PUBLIC_DEV_COMPANY_ID)
      : null
    api
      .get("/auth/me")
      .then((res) => {
        const list: TenantCompany[] = res.data?.companies ?? []
        // Em dev, prefere a empresa do piloto (NEXT_PUBLIC_DEV_COMPANY_ID, ex.:
        // Agora SA id 4) — companies[0] pode ser o "JUNO Dev Tenant" vazio.
        const chosen = (devId ? list.find((c) => c.id === devId) : null) ?? list[0]
        if (active && chosen) setFetchedCompany({ id: chosen.id, name: chosen.name })
      })
      .catch(() => {
        /* sem empresa acessivel — segue sem tenant ativo */
      })
    return () => {
      active = false
    }
  }, [status, selectedCompany, sessionCompany, fetchedCompany])

  const company = selectedCompany ?? sessionCompany ?? fetchedCompany

  return {
    company,
    companyId: company?.id ?? null,
    isLoading: status === "loading",
  }
}
