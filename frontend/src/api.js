import axios from 'axios'

// Prefer relative requests so Vite dev server can proxy /api to the backend.
// If VITE_API_BASE_URL is set (e.g. production), it will be used instead.
const baseURL = import.meta.env.VITE_API_BASE_URL || ''

export const apiClient = axios.create({
    baseURL,
    timeout: 15000,
})
