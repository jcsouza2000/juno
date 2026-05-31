import { DefaultSession } from "next-auth"

type TenantCompany = {
  id: number
  name: string
}

declare module "next-auth" {
  interface Session {
    accessToken?: string
    user: DefaultSession["user"] & {
      id?: string
      role?: string
      companies?: TenantCompany[]
    }
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string
    userId?: string
    role?: string
    companies?: TenantCompany[]
  }
}
