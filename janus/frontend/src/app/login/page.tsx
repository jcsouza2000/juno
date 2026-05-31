"use client"

import { signIn } from "next-auth/react"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const router = useRouter()
  const isDev = process.env.NODE_ENV !== "production"

  useEffect(() => {
    if (isDev) {
      router.replace("/")
    }
  }, [isDev, router])

  if (isDev) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F5F7FA] px-6">
        <div className="rounded-xl border border-gray-100 bg-white p-8 text-center">
          <p className="text-sm font-bold tracking-[0.35em] text-[#C9A959]">JUNO</p>
          <h1 className="mt-3 text-2xl font-bold text-[#0A2342]">Modo desenvolvimento</h1>
          <p className="mt-2 text-sm text-gray-500">Acesso sem senha ativado localmente.</p>
        </div>
      </div>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsSubmitting(true)

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false
    })

    if (result?.error) {
      setError("Email ou senha incorretos")
      setIsSubmitting(false)
    } else {
      router.push("/")
      router.refresh()
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F5F7FA] px-6">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-xl border border-gray-100">
        <div className="text-center">
          <p className="text-sm font-bold tracking-[0.35em] text-[#C9A959]">JUNO</p>
          <h2 className="mt-3 text-3xl font-bold text-[#0A2342]">
            Industrial Diagnostic
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Acesse o ambiente governado de dados, IA e auditoria.
          </p>
        </div>

        {error && <div className="bg-red-50 text-red-700 p-3 rounded">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-[#C9A959] focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-[#C9A959] focus:outline-none"
              required
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md text-sm font-semibold text-white bg-[#0A2342] hover:bg-[#12385F] disabled:opacity-60"
          >
            {isSubmitting ? "Entrando..." : "Entrar"}
          </button>
        </form>
        <p className="text-center text-xs text-gray-500">
          Ambiente SaaS hibrido: dados governados no seu tenant.
        </p>
      </div>
    </div>
  )
}
