import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import api, { errMsg } from '../api/client'
import StatusBadge from '../components/StatusBadge'

const SECTIONS = [
  { key: 'waiting_on_customer', title: 'Waiting on customer', hint: 'Stuck in the automated follow-up loop.' },
  { key: 'escalated_to_you', title: 'Escalated to you', hint: 'Needs a manager or checker decision.' },
  { key: 'auto_approved', title: 'Auto-approved', hint: 'FYI only — no action needed.' },
]

const PIE_COLORS = ['#2F6F5E', '#B5482A', '#D8A84E', '#3F6675', '#9FB9C2', '#6FB096']

export default function Dashboard() {
  const [buckets, setBuckets] = useState(null)
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [dashRes, statsRes] = await Promise.all([api.get('/dashboard'), api.get('/dashboard/stats')])
      setBuckets(dashRes.data)
      setStats(statsRes.data)
    } catch (err) {
      setError(errMsg(err, 'Could not load dashboard.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const statusData = stats
    ? Object.entries(stats.status_counts).map(([name, value]) => ({ name, value }))
    : []
  const damageData = stats
    ? Object.entries(stats.damage_type_counts).map(([name, value]) => ({ name, value }))
    : []

  return (
    <div>
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="text-2xl">Dashboard</h1>
          <p className="text-sm text-navy-400 mt-1">Everything that needs eyes on it, at a glance.</p>
        </div>
        <button onClick={load} className="btn-outline text-xs">Refresh</button>
      </div>

      {error && <div className="text-sm text-clay-600 bg-clay-50 border border-clay-200 rounded-md px-3 py-2 mb-4">{error}</div>}

      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          <StatCard label="Total claims" value={stats.total_claims} />
          <StatCard label="Duplicate claims flagged" value={stats.duplicate_claims} />
          <StatCard label="Approved payout (total)" value={`$${Number(stats.total_approved_payout || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
          <StatCard label="Escalated right now" value={buckets?.escalated_to_you?.length ?? '—'} accent />
        </div>
      )}

      {stats && (statusData.length > 0 || damageData.length > 0) && (
        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="card p-4">
            <h3 className="text-sm font-medium text-navy-600 mb-3">Claims by status</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={statusData} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#2F6F5E" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="card p-4">
            <h3 className="text-sm font-medium text-navy-600 mb-3">Claims by damage type</h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={damageData} dataKey="value" nameKey="name" outerRadius={80} label={{ fontSize: 11 }}>
                  {damageData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {loading && !buckets && <div className="text-sm text-navy-400">Loading…</div>}

      <div className="space-y-8">
        {buckets && SECTIONS.map((section) => (
          <div key={section.key}>
            <div className="flex items-baseline gap-2 mb-2">
              <h2 className="text-lg">{section.title}</h2>
              <span className="text-xs text-navy-400">({buckets[section.key]?.length ?? 0})</span>
            </div>
            <p className="text-xs text-navy-400 mb-3">{section.hint}</p>
            {(!buckets[section.key] || buckets[section.key].length === 0) ? (
              <div className="text-sm text-navy-300 italic">Nothing here.</div>
            ) : (
              <div className="card overflow-hidden">
                <table className="table-shell">
                  <thead>
                    <tr>
                      <th>Claim</th>
                      <th>Policy</th>
                      <th>Claimant</th>
                      <th>Payout</th>
                      <th>Status</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {buckets[section.key].map((c) => (
                      <tr key={c.claim_id}>
                        <td>
                          <Link to={`/claims/${c.claim_id}`} className="text-moss-700 font-mono text-xs hover:underline">
                            {c.claim_id}
                          </Link>
                        </td>
                        <td className="font-mono text-xs">{c.policy_number || '—'}</td>
                        <td className="text-xs">{c.claimant_email}</td>
                        <td className="text-xs">{c.payout != null ? `$${Number(c.payout).toLocaleString()}` : '—'}</td>
                        <td><StatusBadge status={c.status} /></td>
                        <td className="text-xs text-navy-400">{c.created_at ? new Date(c.created_at).toLocaleString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function StatCard({ label, value, accent }) {
  return (
    <div className={`card p-4 ${accent ? 'border-clay-200 bg-clay-50/40' : ''}`}>
      <div className="text-xs text-navy-400 mb-1">{label}</div>
      <div className={`text-2xl font-serif ${accent ? 'text-clay-700' : 'text-navy-800'}`}>{value}</div>
    </div>
  )
}
