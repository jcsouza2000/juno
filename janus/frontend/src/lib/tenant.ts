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
  // Busca a lista de empresas do backend (/auth/me) SEM esperar a sessao do
  // NextAuth: em dev com bypass, /auth/me ja responde com o dev-user e suas
  // empresas. Nao bloquear por status==="loading" evita o seletor travar em "—"
  // quando a sessao fica presa carregando (sem login).
  useEffect(() => {
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
  }, [session])

  const devId = process.env.NEXT_PUBLIC_DEV_COMPANY_ID
    ? Number(process.env.NEXT_PUBLIC_DEV_COMPANY_ID)
    : null
  // Fallback de DEV: empresa de demonstracao sempre disponivel mesmo que
  // /auth/me nao responda (HMR/sessao presa). Garante que o seletor nunca
  // trava em "—" no ambiente local.
  const devFallback: TenantCompany | null =
    devId && process.env.NODE_ENV !== "production"
      ? { id: devId, name: "Agora SA" }
      : null

  let company: TenantCompany | null = null
  if (accessible === null) {
    // Lista ainda carregando: usa otimista (sessao/localStorage/dev) sem travar a UI.
    company = selectedCompany ?? session?.user?.companies?.[0] ?? devFallback ?? null
  } else if (accessible.length > 0) {
    // So' aceita uma empresa que o usuario REALMENTE acessa (evita 403).
    const selValid = selectedCompany
      ? accessible.find((c) => c.id === selectedCompany.id)
      : null
    const devPref = devId ? accessible.find((c) => c.id === devId) : null
    company = selValid ?? devPref ?? accessible[0]
  } else {
    // Lista veio vazia (sessao sem token etc.): usa o fallback de dev.
    company = selectedCompany ?? devFallback ?? null
  }

  // Lista para o seletor: usa a do backend; se vazia, oferece ao menos o dev.
  const companiesForPicker =
    accessible && accessible.length > 0
      ? accessible
      : devFallback
        ? [devFallback]
        : []

  return {
    company,
    companyId: company?.id ?? null,
    // Lista de empresas acessiveis (para o seletor no Header) + setter manual.
    companies: companiesForPicker,
    setCompany: setActiveCompany,
    isLoading: status === "loading" || accessible === null,
  }
}
