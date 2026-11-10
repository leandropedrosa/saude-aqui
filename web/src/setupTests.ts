// Adiciona verificações como toBeInTheDocument() aos testes
import '@testing-library/jest-dom/vitest'

// O jsdom não implementa scrollIntoView; os testes não precisam dele
Element.prototype.scrollIntoView = () => {}
