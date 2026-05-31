/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  devIndicators: false,
  
  images: {
    unoptimized: true, // Para Docker, evita dependência do Sharp
  },
  
  // Headers de segurança
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
        ],
      },
    ]
  },
  
  // O frontend usa src/lib/api.ts para falar com o FastAPI.
  // Nao reescreva /api/* aqui, pois /api/auth/* pertence ao NextAuth.
}

module.exports = nextConfig
