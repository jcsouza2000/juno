"use client"

import { signOut, useSession } from "next-auth/react"
import { useActiveCompany } from "@/lib/tenant"

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
  const user = session?.user

  return (
    <header className="bg-white border-b border-gray-100 h-16 flex items-center justify-between px-8 ml-64">
      <div>
        <h2 className="text-lg font-semibold text-gray-800">JUNO Industrial Diagnostic v0.3.2</h2>
      </div>
      <div className="flex items-center gap-4">
        <span className="px-3 py-1 rounded-full bg-[#C9A959]/10 text-[#8A6D1D] text-xs font-bold uppercase">
          {company ? company.name : "SaaS Hibrido"}
        </span>
        <div className="text-right">
          <p className="text-sm font-semibold text-gray-800">{user?.name || user?.email || "Usuario"}</p>
          <p className="text-xs text-gray-500 uppercase">{user?.role || "sem perfil"}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-[#0A2342] text-white flex items-center justify-center text-xs font-bold">
          {initials(user?.name, user?.email)}
        </div>
        <button
          type="button"
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="text-xs font-semibold text-gray-500 hover:text-[#0A2342]"
        >
          Sair
        </button>
      </div>
    </header>
  );
}
