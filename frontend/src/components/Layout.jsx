import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', roles: ['admin', 'manager', 'checker'] },
  { to: '/claims', label: 'Claims', roles: ['admin', 'manager', 'checker'] },
  { to: '/claims/new', label: 'New claim', roles: ['admin', 'manager', 'checker'] },
  { to: '/policies', label: 'Policies', roles: ['admin', 'manager', 'checker'] },
  { to: '/poller', label: 'Inbox poller', roles: ['admin', 'manager', 'checker'] },
  { to: '/sql', label: 'Query database', roles: ['admin', 'manager'] },
  { to: '/settings', label: 'Settings', roles: ['admin', 'manager'] },
  { to: '/users', label: 'Users', roles: ['admin'] },
]

export default function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen flex bg-paper">
      <aside className="w-60 shrink-0 bg-navy-700 text-paper flex flex-col">
        <div className="px-5 py-6 border-b border-white/10">
          <div className="font-serif text-lg leading-tight text-white">FNOL Console</div>
          <div className="text-xs text-navy-200 mt-0.5">Claims intake operations</div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV_ITEMS.filter((item) => !user || item.roles.includes(user.role)).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/claims'}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive ? 'bg-white/10 text-white font-medium' : 'text-navy-100 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-white/10">
          <div className="text-sm text-white truncate">{user?.full_name || user?.email}</div>
          <div className="text-xs text-navy-300 capitalize mb-2">{user?.role}</div>
          <button onClick={logout} className="text-xs text-navy-200 hover:text-white underline underline-offset-2">
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        <div className="max-w-6xl mx-auto px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
