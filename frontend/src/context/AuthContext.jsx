import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import api, { errMsg } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem('fnol_user')
    return raw ? JSON.parse(raw) : null
  })
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('fnol_token')
    if (!token) {
      setReady(true)
      return
    }
    api.get('/auth/me')
      .then((res) => {
        setUser(res.data)
        localStorage.setItem('fnol_user', JSON.stringify(res.data))
      })
      .catch(() => {
        localStorage.removeItem('fnol_token')
        localStorage.removeItem('fnol_user')
        setUser(null)
      })
      .finally(() => setReady(true))
  }, [])

  const login = useCallback(async (email, password) => {
    try {
      const form = new URLSearchParams()
      form.append('username', email)
      form.append('password', password)
      const res = await api.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      localStorage.setItem('fnol_token', res.data.access_token)
      const me = { email: res.data.email, role: res.data.role, full_name: res.data.full_name }
      localStorage.setItem('fnol_user', JSON.stringify(me))
      setUser(me)
      return { ok: true }
    } catch (err) {
      return { ok: false, error: errMsg(err, 'Login failed.') }
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('fnol_token')
    localStorage.removeItem('fnol_user')
    setUser(null)
    window.location.href = '/login'
  }, [])

  const isManagerOrAdmin = user && (user.role === 'manager' || user.role === 'admin')
  const isAdmin = user && user.role === 'admin'

  return (
    <AuthContext.Provider value={{ user, ready, login, logout, isManagerOrAdmin, isAdmin }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
