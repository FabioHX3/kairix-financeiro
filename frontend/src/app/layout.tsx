import type { Metadata, Viewport } from "next"
import { Poppins } from "next/font/google"
import "./globals.css"
import { QueryProvider } from "@/providers/query-provider"
import { ToastProvider } from "@/providers/toast-provider"

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-poppins",
})

export const metadata: Metadata = {
  title: {
    default: "Kairix Financeiro",
    template: "%s | Kairix Financeiro",
  },
  description: "Assistente financeiro inteligente com IA. Controle suas finanças pelo WhatsApp.",
  keywords: ["financeiro", "controle financeiro", "whatsapp", "ia", "inteligência artificial"],
  authors: [{ name: "Kairix" }],
  icons: {
    icon: "/assets/logo.png",
    apple: "/assets/logo.png",
  },
}

export const viewport: Viewport = {
  themeColor: "#121212",
  width: "device-width",
  initialScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="pt-BR" className="dark">
      <body className={`${poppins.variable} font-sans antialiased`}>
        <QueryProvider>
          {children}
          <ToastProvider />
        </QueryProvider>
      </body>
    </html>
  )
}
