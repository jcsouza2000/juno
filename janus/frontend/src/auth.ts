import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
const DEV_AUTH_SECRET = "smart-juno-local-auth-secret-only-for-development-32-chars"

// Em producao real, AUTH_SECRET/NEXTAUTH_SECRET DEVEM vir do ambiente.
// O fallback DEV_AUTH_SECRET garante que o launcher local nunca quebre o
// /api/auth/session com 500 quando a env nao chega ao processo do Next.
export const { handlers, signIn, signOut, auth } = NextAuth({
  // NextAuth v5 fora da Vercel exige trustHost; sem isso o /api/auth/session
  // retorna 500 ("problem with the server configuration") em 127.0.0.1/local.
  trustHost: true,
  secret:
    process.env.AUTH_SECRET ||
    process.env.NEXTAUTH_SECRET ||
    DEV_AUTH_SECRET,
  providers: [
    Credentials({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Senha", type: "password" }
      },
      async authorize(credentials) {
        const res = await fetch(`${API_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            username: String(credentials?.email ?? ""),
            password: String(credentials?.password ?? "")
          })
        })

        if (!res.ok) return null

        const data = await res.json()
        return {
          id: String(data.user.id),
          email: data.user.email,
          name: data.user.full_name,
          role: data.user.role,
          companies: data.user.companies ?? [],
          accessToken: data.access_token
        }
      }
    })
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = (user as { accessToken?: string }).accessToken
        token.userId = user.id
        token.role = (user as { role?: string }).role
        token.companies = (user as { companies?: { id: number; name: string }[] }).companies
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.userId as string
        ;(session.user as { role?: string }).role = token.role as string
        ;(session.user as { companies?: { id: number; name: string }[] }).companies =
          token.companies as { id: number; name: string }[]
      }
      ;(session as { accessToken?: string }).accessToken = token.accessToken as string
      return session
    }
  },
  pages: {
    signIn: "/login"
  }
})
