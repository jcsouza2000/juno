import { auth } from "@/auth"
import { NextResponse } from "next/server"

export default auth((req) => {
  if (process.env.NODE_ENV !== "production") {
    return NextResponse.next()
  }

  const isLoggedIn = !!req.auth
  const isAuthPage = req.nextUrl.pathname.startsWith("/login")

  if (!isLoggedIn && !isAuthPage) {
    return NextResponse.redirect(new URL("/login", req.url))
  }

  if (isLoggedIn && isAuthPage) {
    return NextResponse.redirect(new URL("/", req.url))
  }

  return NextResponse.next()
})

export const config = {
  // Exclui TODO o /_next (nao so static/image): rodar o middleware em
  // /_next/webpack-hmr quebra o WebSocket de hot-reload
  // (ERR_INVALID_HTTP_RESPONSE) e corrompe a hidratacao do app em dev.
  matcher: ["/((?!api|_next|favicon.ico|templates).*)"],
}
