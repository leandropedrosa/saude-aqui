/// <reference types="vite/client" />

// Variáveis lidas em tempo de build (opcionais). Ver .env.example na raiz.
interface ImportMetaEnv {
  readonly VITE_TILES_URL?: string
  readonly VITE_TILES_ATRIBUICAO?: string
}
