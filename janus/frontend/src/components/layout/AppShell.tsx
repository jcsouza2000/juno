"use client"

import { usePathname } from "next/navigation"
import Header from "@/components/layout/Header"
import Sidebar from "@/components/layout/Sidebar"

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isAuthPage = pathname?.startsWith("/login")

  if (isAuthPage) {
    return <main>{children}</main>
  }

  return (
    <div className="flex">
      <Sidebar />
      <div className="flex-1 flex flex-col min-h-screen">
        <Header />
        <main className="flex-1 p-8 ml-64 bg-[#F5F7FA]">{children}</main>
      </div>
    </div>
  )
}
