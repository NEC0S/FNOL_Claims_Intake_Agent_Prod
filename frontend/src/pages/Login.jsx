import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const DEMO_EMAIL = 'admin@example.com'
const DEMO_PASSWORD = '12344321'
const BACKEND_HEALTH_URL = 'https://fnol-backend-ew99.onrender.com/api/health'

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState(DEMO_EMAIL)
  const [password, setPassword] = useState(DEMO_PASSWORD)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (user) return <Navigate to="/dashboard" replace />

  const handleWakeBackend = () => {
    window.open(BACKEND_HEALTH_URL, '_blank', 'noopener,noreferrer')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    const res = await login(email, password)
    setLoading(false)

    if (res.ok) {
      navigate('/dashboard')
    } else {
      setError(res.error)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-navy-800 px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="font-serif text-2xl text-white">FNOL Console</div>
          <div className="text-sm text-navy-300 mt-1">Claims intake operations</div>
        </div>

        <div className="card bg-white p-6 space-y-5">
          <div className="rounded-md border border-wheat-200 bg-wheat-50 px-4 py-3">
            <div className="text-sm font-medium text-navy-800">Start the demo</div>
            <p className="text-xs text-navy-500 mt-1 leading-relaxed">
              The backend is hosted separately on Render and may be sleeping.
              If login does not work, wake the backend first.
            </p>
            <button
              type="button"
              onClick={handleWakeBackend}
              className="btn-outline w-full mt-3"
            >
              Wake up backend
            </button>
            <p className="text-[11px] text-navy-400 mt-2 text-center">
              A new tab will open the backend health check. Wait a few seconds, then return here.
            </p>
          </div>

          <div>
            <div className="text-sm font-medium text-navy-800">Demo credentials</div>
            <p className="text-xs text-navy-500 mt-1">
              The credentials are already filled in below.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                className="input"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="label">Password</label>
              <div className="relative">
                <input
                  className="input pr-16"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-medium text-navy-500 hover:text-navy-800 px-2 py-1"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {error && (
              <div className="text-sm text-clay-600 bg-clay-50 border border-clay-200 rounded-md px-3 py-2">
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="rounded-md bg-navy-50 border border-navy-100 px-3 py-2.5 text-xs text-navy-600">
            <div className="font-medium text-navy-700">Demo login</div>
            <div className="mt-1">
              Email: <span className="font-mono">{DEMO_EMAIL}</span>
            </div>
            <div>
              Password: <span className="font-mono">{DEMO_PASSWORD}</span>
            </div>
          </div>
        </div>

        <p className="text-[11px] text-navy-400 text-center mt-4 leading-relaxed">
          This is a public demo account. Do not use real or sensitive credentials.
        </p>
      </div>
    </div>
  )
}
