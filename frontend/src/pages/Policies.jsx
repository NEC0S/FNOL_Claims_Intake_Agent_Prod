import { useEffect, useState } from 'react'
import api, { errMsg } from '../api/client'
import { useAuth } from '../context/AuthContext'

const EMPTY_FORM = {
  policy_number: '', holder_name: '', holder_email: '', address: '',
  coverage_limit: '', deductible: '', start_date: '', end_date: '',
}

export default function Policies() {
  const { isManagerOrAdmin } = useAuth()
  const [policies, setPolicies] = useState([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/policies', { params: { search: search || undefined, limit: 200 } })
      setPolicies(res.data.policies)
      setTotal(res.data.total)
    } catch (err) {
      setError(errMsg(err, 'Could not load policies.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.put('/policies', {
        ...form,
        coverage_limit: parseFloat(form.coverage_limit),
        deductible: parseFloat(form.deductible),
        holder_email: form.holder_email || null,
      })
      setForm(EMPTY_FORM)
      setShowForm(false)
      await load()
    } catch (err) {
      setError(errMsg(err, 'Could not save policy.'))
    } finally {
      setSaving(false)
    }
  }

  const edit = (p) => {
    setForm({
      policy_number: p.policy_number, holder_name: p.holder_name, holder_email: p.holder_email || '',
      address: p.address || '', coverage_limit: p.coverage_limit, deductible: p.deductible,
      start_date: p.start_date, end_date: p.end_date,
    })
    setShowForm(true)
  }

  return (
    <div>
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="text-2xl">Policies</h1>
          <p className="text-sm text-navy-400 mt-1">{total} polic{total === 1 ? 'y' : 'ies'} on file.</p>
        </div>
        {isManagerOrAdmin && (
          <button className="btn-accent text-sm" onClick={() => { setForm(EMPTY_FORM); setShowForm((s) => !s) }}>
            {showForm ? 'Close' : 'Add / edit policy'}
          </button>
        )}
      </div>

      {showForm && (
        <form onSubmit={submit} className="card p-5 mb-6 grid grid-cols-2 gap-3">
          <Field label="Policy number" k="policy_number" form={form} setForm={setForm} required />
          <Field label="Holder name" k="holder_name" form={form} setForm={setForm} required />
          <Field label="Holder email" k="holder_email" form={form} setForm={setForm} type="email" />
          <Field label="Address" k="address" form={form} setForm={setForm} />
          <Field label="Coverage limit ($)" k="coverage_limit" form={form} setForm={setForm} type="number" step="0.01" required />
          <Field label="Deductible ($)" k="deductible" form={form} setForm={setForm} type="number" step="0.01" required />
          <Field label="Start date" k="start_date" form={form} setForm={setForm} type="date" required />
          <Field label="End date" k="end_date" form={form} setForm={setForm} type="date" required />
          <div className="col-span-2 flex gap-2">
            <button className="btn-accent text-sm" disabled={saving}>{saving ? 'Saving…' : 'Save policy'}</button>
          </div>
        </form>
      )}

      {error && <div className="text-sm text-clay-600 bg-clay-50 border border-clay-200 rounded-md px-3 py-2 mb-4">{error}</div>}

      <div className="card p-4 mb-4">
        <form onSubmit={(e) => { e.preventDefault(); load() }} className="flex gap-2">
          <input className="input flex-1" placeholder="Search policy number, holder name, or email…" value={search} onChange={(e) => setSearch(e.target.value)} />
          <button className="btn-outline text-sm">Search</button>
        </form>
      </div>

      <div className="card overflow-hidden">
        <table className="table-shell">
          <thead>
            <tr>
              <th>Policy</th><th>Holder</th><th>Coverage</th><th>Deductible</th><th>Window</th><th></th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={6} className="text-center text-navy-400 py-6">Loading…</td></tr>}
            {!loading && policies.length === 0 && <tr><td colSpan={6} className="text-center text-navy-400 py-6">No policies yet.</td></tr>}
            {policies.map((p) => (
              <tr key={p.policy_number}>
                <td className="font-mono text-xs">{p.policy_number}</td>
                <td className="text-xs">{p.holder_name}<br /><span className="text-navy-400">{p.holder_email}</span></td>
                <td className="text-xs">${Number(p.coverage_limit).toLocaleString()}</td>
                <td className="text-xs">${Number(p.deductible).toLocaleString()}</td>
                <td className="text-xs">{p.start_date} → {p.end_date}</td>
                <td>{isManagerOrAdmin && <button className="btn-ghost text-xs" onClick={() => edit(p)}>Edit</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Field({ label, k, form, setForm, type = 'text', ...rest }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input
        className="input"
        type={type}
        value={form[k]}
        onChange={(e) => setForm((p) => ({ ...p, [k]: e.target.value }))}
        {...rest}
      />
    </div>
  )
}
