import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// base './' lets the built site work from a GitHub Pages subpath (user.github.io/repo/)
export default defineConfig({
  base: './',
  plugins: [react()],
})
