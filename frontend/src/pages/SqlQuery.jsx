import { useEffect, useState } from 'react'
import api, { errMsg } from '../api/client'

const EXAMPLES = [
  { label: 'All escalated claims', sql: "select claim_id, policy_number, claimant_email, payout, created_at from claims where status = 'escalate_to_manager' order by created_at desc" },
  { label: 'Payout total by status', sql: 'select status, count(*) as n, sum(payout) as total_payout from claims group by status order by total_payout desc nulls last' },
  { label: 'Claims with high risk score', sql: "select claim_id, claimant_email, risk_notes->>'risk_score' as risk_score, risk_notes->>'notes' as notes from claims where (risk_notes->>'risk_score')::float >= 0.3" },
  { label: 'Recent activity events', sql: 'select claim_id, event_type, actor, created_at from claim_events order by created_at desc limit 50' },
]

export default function SqlQuery() {
  const [sql, setSql] = useState(EXAMPLES[0].sql)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [tables, setTables] = useState([])

  useEffect(() => {
    api.get('/sql/tables').then((res) => setTables(res.data)).catch(() => {})
  }, [])

  const run = async (e) => {
    e?.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await api.post('/sql/query', { sql, limit: 500 })
      setResult(res.data)
    } catch (err) {
      setError(errMsg(err, 'Query failed.'))
    } finally {
      setLoading(false)
    }
  }

  const downloadCsv = () => {
    if (!result) return
    const header = result.columns.join(',')
    const rows = result.rows.map((r) => r.map((v) => `"${String(v ?? '').replaceAll('"', '""')}"`).join(','))
    const csv = [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'query_result.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <h1 className="text-2xl mb-1">Query database</h1>
      <p className="text-sm text-navy-400 mb-6">
        Read-only SQL access for pulling data out of the claims database. Only SELECT / WITH
        statements are allowed — anything else is rejected before it reaches the database.
      </p>

      <div className="grid grid-cols-4 gap-6">
        <div className="col-span-3">
          <form onSubmit={run} className="card p-4 mb-4">
            <textarea
              className="input font-mono text-xs"
              rows={8}
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              spellCheck={false}
            />
            <div className="flex items-center gap-2 mt-3">
              <button className="btn-primary text-sm" disabled={loading}>{loading ? 'Running…' : 'Run query'}</button>
              {result && <button type="button" className="btn-outline text-sm" onClick={downloadCsv}>Download CSV</button>}
              {result && <span className="text-xs text-navy-400">{result.row_count} row{result.row_count === 1 ? '' : 's'}{result.truncated ? ' (truncated)' : ''}</span>}
            </div>
          </form>

          {error && <div className="text-sm text-clay-600 bg-clay-50 border border-clay-200 rounded-md px-3 py-2 mb-4">{error}</div>}

          {result && (
            <div className="card overflow-auto max-h-[520px]">
              <table className="table-shell">
                <thead>
                  <tr>{result.columns.map((c) => <th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {result.rows.map((row, i) => (
                    <tr key={i}>
                      {row.map((v, j) => <td key={j} className="text-xs whitespace-nowrap">{v === null ? <span className="text-navy-300">null</span> : String(v)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="card p-4">
            <h3 className="text-sm font-medium text-navy-600 mb-2">Example queries</h3>
            <div className="space-y-1">
              {EXAMPLES.map((ex) => (
                <button key={ex.label} className="block text-left text-xs text-moss-700 hover:underline" onClick={() => setSql(ex.sql)}>
                  {ex.label}
                </button>
              ))}
            </div>
          </div>
          <div className="card p-4">
            <h3 className="text-sm font-medium text-navy-600 mb-2">Tables</h3>
            <ul className="text-xs text-navy-500 space-y-1 font-mono">
              {tables.map((t) => <li key={t.table_name}>{t.table_name} <span className="text-navy-300">({t.column_count} cols)</span></li>)}
              {tables.length === 0 && <li className="text-navy-300 italic font-sans">DATABASE_URL not configured on the backend.</li>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
