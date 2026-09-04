import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'

import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ClaimsList from './pages/ClaimsList'
import ClaimDetail from './pages/ClaimDetail'
import NewClaim from './pages/NewClaim'
import Policies from './pages/Policies'
import Poller from './pages/Poller'
import SqlQuery from './pages/SqlQuery'
import Settings from './pages/Settings'
import Users from './pages/Users'

function ProtectedRoute({ children, roles }) {
  const { user, ready } = useAuth()
  if (!ready) return <div className="p-8 text-navy-400 text-sm">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/claims" element={<ClaimsList />} />
        <Route path="/claims/new" element={<NewClaim />} />
        <Route path="/claims/:claimId" element={<ClaimDetail />} />
        <Route path="/policies" element={<Policies />} />
        <Route path="/poller" element={<Poller />} />
        <Route
          path="/sql"
          element={
            <ProtectedRoute roles={['admin', 'manager']}>
              <SqlQuery />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute roles={['admin', 'manager']}>
              <Settings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/users"
          element={
            <ProtectedRoute roles={['admin']}>
              <Users />
            </ProtectedRoute>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
