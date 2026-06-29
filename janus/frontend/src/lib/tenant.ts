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
  const [accessible, setAccessible] = useState<TenantCompany[] | null>(null)

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

  // Lista AUTORITATIVA de empresas que o contexto de auth ATUAL pode acessar.
  // Buscada do backend (/auth/me) com a mesma autenticacao usada nos uploads —
  // assim a empresa ativa nunca fica "fantasma" (causando 403 Acesso negado).
  // Em dev com JUNO_DEV_AUTH_BYPASS, retorna o dev-user com suas empresas reais.
  useEffect(() => {
    if (status === "loading") return
    let active = true
    api
      .get("/auth/me")
      .then((res) => {
        if (active) setAccessible(res.data?.companies ?? [])
      })
      .catch(() => {
        if (active) setAccessible([])
      })
    return () => {
      active = false
    }
  }, [status, session])

  const devId = process.env.NEXT_PUBLIC_DEV_COMPANY_ID
    ? Number(process.env.NEXT_PUBLIC_DEV_COMPANY_ID)
    : null

  let company: TenantCompany | null = null
  if (accessible === null) {
    // Lista ainda carregando: usa otimista (sessao/localStorage) sem travar a UI.
    company = selectedCompany ?? session?.user?.companies?.[0] ?? null
  } else if (accessible.length > 0) {
    // So' aceita uma empresa que o usuario REALMENTE acessa (evita 403).
    const selValid = selectedCompany
      ? accessible.find((c) => c.id === selectedCompany.id)
      : null
    const devPref = devId ? accessible.find((c) => c.id === devId) : null
    company = selValid ?? devPref ?? accessible[0]
  }

  return {
    company,
    companyId: company?.id ?? null,
    // Lista de empresas acessiveis (para o seletor no Header) + setter manual.
    companies: accessible ?? [],
    setCompany: setActiveCompany,
    isLoading: status === "loading" || accessible === null,
  }
}
