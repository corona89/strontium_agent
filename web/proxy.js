import { NextResponse } from 'next/server'

const PUBLIC_PATHS = new Set(['/login'])

export function proxy(request) {
  const { pathname } = request.nextUrl
  const hasToken = request.cookies.has('access_token')

  if (PUBLIC_PATHS.has(pathname)) {
    if (hasToken) return NextResponse.redirect(new URL('/', request.url))
    return NextResponse.next()
  }

  if (!hasToken) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|env-config.js).*)'],
}
