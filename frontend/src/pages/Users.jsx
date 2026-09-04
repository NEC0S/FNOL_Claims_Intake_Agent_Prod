import { useEffect, useState } from 'react'
import api, { errMsg } from '../api/client'

const EMPTY = { email: '', password: '', full_name: '', role: 'checker' }

export default function Users() {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = async () => {
    try {
      const res = await api.get('/auth/users')
      setUsers(res.data)
    } catch (err) {
      setError(errMsg(err, 'Could not load users.'))
    }
  }

  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post('/auth/users', form)
      setForm(EMPTY)
      await load()
    } catch (err) {
      setError(errMsg(err, 'Could not create user.'))
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (u) => {
    await api.patch(`/auth/users/${u.id}/${u.is_active ? 'deactivate' : 'activate'}`)
    await load()
  }

  const changeRole = async (u, role) => {
    await api.patch(`/auth/users/${u.id}/role`, null, { params: { role } })
    await load()
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl mb-1">Users</h1>
      <p className="text-sm text-navy-400 mb-6">Manage manager and checker accounts. Admin only.</p>

      <form onSubmit={submit} className="card p-5 mb-6 grid grid-cols-2 gap-3">
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" required value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
        </div>
        <div>
          <label className="label">Password</label>
          <input className="input" type="password" required value={form.password} onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))} />
        </div>
        <div>
          <label className="label">Full name</label>
          <input className="input" value={form.full_name} onChange={(e) => setForm((p) => ({ ...p, full_name: e.target.value }))} />
        </div>
        <div>
          <label className="label">Role</label>
          <select className="input" value={form.role} onChange={(e) => setForm((p) => ({ ...p, role: e.target.value }))}>
            <option value="checker">Checker</option>
            <option value="manager">Manager</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        {error && <div className="col-span-2 text-sm text-clay-600 bg-clay-50 border border-clay-200 rounded-md px-3 py-2">{error}</div>}
        <div className="col-span-2">
          <button className="btn-accent text-sm" disabled={saving}>{saving ? 'Creating…' : 'Create user'}</button>
        </div>
      </form>

      <div className="card overflow-hidden">
        <table className="table-shell">
          <thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td className="text-xs">{u.email}</td>
                <td className="text-xs">{u.full_name || '—'}</td>
                <td className="text-xs">
                  <select className="input py-1 text-xs" value={u.role} onChange={(e) => changeRole(u, e.target.value)}>
                    <option value="checker">Checker</option>
                    <option value="manager">Manager</option>
                    <option value="admin">Admin</option>
                  </select>
                </td>
                <td className="text-xs">{u.is_active ? <span className="badge bg-moss-50 text-moss-700">Active</span> : <span className="badge bg-navy-50 text-navy-400">Inactive</span>}</td>
                <td><button className="btn-ghost text-xs" onClick={() => toggleActive(u)}>{u.is_active ? 'Deactivate' : 'Activate'}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
