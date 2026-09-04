import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { errMsg } from '../api/client'
import StatusBadge from '../components/StatusBadge'

const STATUS_OPTIONS = [
  'new', 'awaiting_info', 'needs_manual_followup', 'escalate_to_manager',
  'rejected_unknown_policy', 'auto_approve', 'manager_approved', 'manager_rejected', 'superseded',
]

export default function ClaimsList() {
  const [claims, setClaims] = useState([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState([])
  const [includeSuperseded, setIncludeSuperseded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const params = { limit: 200, include_superseded: includeSuperseded }
      if (search.trim()) params.search = search.trim()
      if (statusFilter.length) params.status = statusFilter.join(',')
      const res = await api.get('/claims', { params })
      setClaims(res.data.claims)
      setTotal(res.data.total)
    } catch (err) {
      setError(errMsg(err, 'Could not load claims.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [statusFilter, includeSuperseded])

  const toggleStatus = (s) => {
    setStatusFilter((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]))
  }

  return (
    <div>
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="text-2xl">Claims</h1>
          <p className="text-sm text-navy-400 mt-1">{total} claim{total === 1 ? '' : 's'} on file.</p>
        </div>
        <Link to="/claims/new" className="btn-accent text-sm">New claim</Link>
      </div>

      <div className="card p-4 mb-4 space-y-3">
        <form onSubmit={(e) => { e.preventDefault(); load() }} className="flex gap-2">
          <input
            className="input flex-1"
            placeholder="Search claim ID, policy number, or claimant email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="btn-outline text-sm">Search</button>
        </form>
        <div className="flex flex-wrap gap-1.5 items-center">
          <span className="text-xs text-navy-400 mr-1">Status:</span>
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => toggleStatus(s)}
              className={`badge border transition-colors ${
                statusFilter.includes(s)
                  ? 'bg-navy-700 text-white border-navy-700'
                  : 'bg-white text-navy-500 border-navy-200 hover:border-navy-400'
              }`}
            >
              {s.replaceAll('_', ' ')}
            </button>
          ))}
          <label className="flex items-center gap-1.5 text-xs text-navy-500 ml-3">
            <input type="checkbox" checked={includeSuperseded} onChange={(e) => setIncludeSuperseded(e.target.checked)} />
            include superseded
          </label>
        </div>
      </div>

      {error && <div className="text-sm text-clay-600 bg-clay-50 border border-clay-200 rounded-md px-3 py-2 mb-4">{error}</div>}

      <div className="card overflow-hidden">
        <table className="table-shell">
          <thead>
            <tr>
              <th>Claim</th>
              <th>Policy</th>
              <th>Claimant</th>
              <th>Damage type</th>
              <th>Payout</th>
              <th>Status</th>
              <th>Source</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={8} className="text-center text-navy-400 py-6">Loading…</td></tr>
            )}
            {!loading && claims.length === 0 && (
              <tr><td colSpan={8} className="text-center text-navy-400 py-6">No claims match these filters.</td></tr>
            )}
            {claims.map((c) => (
              <tr key={c.claim_id}>
                <td><Link to={`/claims/${c.claim_id}`} className="text-moss-700 font-mono text-xs hover:underline">{c.claim_id}</Link></td>
                <td className="font-mono text-xs">{c.policy_number || '—'}</td>
                <td className="text-xs">{c.claimant_email}</td>
                <td className="text-xs">{c.damage_type || '—'}</td>
                <td className="text-xs">{c.payout != null ? `$${Number(c.payout).toLocaleString()}` : '—'}</td>
                <td><StatusBadge status={c.status} /></td>
                <td className="text-xs text-navy-400">{c.source}</td>
                <td className="text-xs text-navy-400">{c.created_at ? new Date(c.created_at).toLocaleString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
