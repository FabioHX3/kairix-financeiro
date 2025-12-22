import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Public paths that don't require authentication
const publicPaths = ['/login', '/cadastro']

// Static files and API routes to skip
const skipPaths = ['/api', '/_next', '/assets', '/favicon.ico']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Skip middleware for static files and API routes
  if (skipPaths.some(path => pathname.startsWith(path))) {
    return NextResponse.next()
  }

  // Check for auth token in cookies or localStorage header
  const token = request.cookies.get('token')?.value

  // Check if path is public
  const isPublicPath = publicPaths.some(path => pathname.startsWith(path))

  // If authenticated and trying to access auth pages, redirect to dashboard
  if (token && isPublicPath) {
    return NextResponse.redirect(new URL('/', request.url))
  }

  // If not authenticated and trying to access protected pages, redirect to login
  if (!token && !isPublicPath) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('redirect', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
}
