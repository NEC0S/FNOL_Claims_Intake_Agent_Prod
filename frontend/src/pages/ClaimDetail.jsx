import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import api, { errMsg } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import { useAuth } from '../context/AuthContext'

export default function ClaimDetail() {
  const { claimId } = useParams()
  const { isManagerOrAdmin } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [notes, setNotes] = useState('')
  const [acting, setActing] = useState(false)
  const [actionMsg, setActionMsg] = useState('')
  const [resumeText, setResumeText] = useState('')
  const [resuming, setResuming] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [editValues, setEditValues] = useState({})

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get(`/claims/${claimId}`)
      setData(res.data)
    } catch (err) {
      setError(errMsg(err, 'Could not load claim.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [claimId])

  const runAction = async (action) => {
    setActing(true)
    setActionMsg('')
    try {
      const res = await api.post(`/claims/${claimId}/review`, { action, notes: notes || null })
      setActionMsg(`Done — new status: ${res.data.new_status || 'unchanged'}`)
      setNotes('')
      await load()
    } catch (err) {
      setActionMsg(errMsg(err, 'Action failed.'))
    } finally {
      setActing(false)
    }
  }

  const runResume = async (e) => {
    e.preventDefault()
    setResuming(true)
    setActionMsg('')
    try {
      await api.post(`/claims/${claimId}/resume`, { followup_email_text: resumeText })
      setResumeText('')
      setActionMsg('Follow-up reply processed through the pipeline.')
      await load()
    } catch (err) {
      setActionMsg(errMsg(err, 'Resume failed.'))
    } finally {
      setResuming(false)
    }
  }

  const startEdit = () => {
    setEditValues({
      status: data.claim.status || '',
      policy_number: data.claim.policy_number || '',
      incident_date: data.claim.incident_date || '',
      location: data.claim.location || '',
      description: data.claim.description || '',
      fault_claimed: data.claim.fault_claimed || '',
      damage_type: data.claim.damage_type || '',
      damage_estimate: data.claim.damage_estimate ?? '',
      payout: data.claim.payout ?? '',
    })
    setEditMode(true)
  }

  const saveEdit = async () => {
    setActing(true)
    try {
      const payload = {}
      Object.entries(editValues).forEach(([k, v]) => {
        if (v === '') return
        if (k === 'damage_estimate' || k === 'payout') payload[k] = parseFloat(v)
        else payload[k] = v
      })
      await api.patch(`/claims/${claimId}`, payload)
      setEditMode(false)
      await load()
    } catch (err) {
      setActionMsg(errMsg(err, 'Save failed.'))
    } finally {
      setActing(false)
    }
  }

  if (loading) return <div className="text-navy-400 text-sm">Loading…</div>
  if (error) return <div className="text-sm text-clay-600 bg-clay-50 border border-clay-200 rounded-md px-3 py-2">{error}</div>
  if (!data) return null

  const { claim, events, reviews, emails } = data
  const decision = claim.decision || {}
  const coverage = claim.coverage_check || {}
  const weather = claim.weather_check || {}
  const risk = claim.risk_notes || {}

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <Link to="/claims" className="text-xs text-navy-400 hover:text-navy-600">&larr; All claims</Link>
          <h1 className="text-2xl font-mono mt-1">{claim.claim_id}</h1>
          <div className="mt-2 flex items-center gap-2">
            <StatusBadge status={claim.status} />
            {claim.is_duplicate && <span className="badge bg-clay-50 text-clay-700 border border-clay-200">Duplicate/supersedes prior claim</span>}
            {claim.superseded_by && <span className="badge bg-navy-50 text-navy-400 border border-navy-100">Superseded by {claim.superseded_by}</span>}
          </div>
        </div>
        {isManagerOrAdmin && !editMode && (
          <button className="btn-outline text-xs" onClick={startEdit}>Edit fields</button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-6">
          <section className="card p-5">
            <h2 className="text-base mb-3">Claim details</h2>
            {editMode ? (
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(editValues).map(([k, v]) => (
                  <div key={k}>
                    <label className="label">{k.replaceAll('_', ' ')}</label>
                    <input className="input" value={v} onChange={(e) => setEditValues((p) => ({ ...p, [k]: e.target.value }))} />
                  </div>
                ))}
                <div className="col-span-2 flex gap-2 pt-2">
                  <button className="btn-accent text-sm" disabled={acting} onClick={saveEdit}>Save changes</button>
                  <button className="btn-ghost text-sm" onClick={() => setEditMode(false)}>Cancel</button>
                </div>
              </div>
            ) : (
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <Field label="Policy number" value={claim.policy_number} mono />
                <Field label="Claimant email" value={claim.claimant_email} />
                <Field label="Incident date" value={claim.incident_date} />
                <Field label="Location" value={claim.location} />
                <Field label="Damage type" value={claim.damage_type} />
                <Field label="Fault claimed" value={claim.fault_claimed} />
                <Field label="Damage estimate" value={claim.damage_estimate != null ? `$${Number(claim.damage_estimate).toLocaleString()}` : null} />
                <Field label="Payout" value={claim.payout != null ? `$${Number(claim.payout).toLocaleString()}` : null} />
                <Field label="Follow-ups sent" value={claim.followup_count} />
                <Field label="Source" value={claim.source} />
                <div className="col-span-2">
                  <Field label="Description" value={claim.description} block />
                </div>
              </dl>
            )}
          </section>

          <section className="card p-5">
            <h2 className="text-base mb-3">Automated checks</h2>
            <div className="space-y-3 text-sm">
              <CheckRow title="Coverage window" ok={coverage.in_window} detail={coverage.reason} />
              <CheckRow
                title="Weather cross-check"
                ok={weather.matches_claim}
                detail={weather.note || `Condition: ${weather.condition || 'unknown'}${weather.precipitation_mm != null ? `, ${weather.precipitation_mm}mm precipitation` : ''}`}
              />
              <CheckRow
                title="Language risk score"
                ok={risk.risk_score != null ? risk.risk_score < 0.3 : null}
                detail={risk.notes ? `Score ${risk.risk_score} — ${risk.notes}` : 'Not yet scored'}
              />
            </div>
          </section>

          <section className="card p-5">
            <h2 className="text-base mb-3">Decision</h2>
            <div className="text-sm">
              <div className="mb-2"><StatusBadge status={decision.decision} /></div>
              <ul className="list-disc list-inside text-navy-600 space-y-1">
                {(decision.reasons || []).map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          </section>

          {claim.report && (
            <section className="card p-5">
              <h2 className="text-base mb-3">Adjudicator report</h2>
              <p className="text-sm text-navy-700 whitespace-pre-wrap leading-relaxed">{claim.report}</p>
            </section>
          )}

          <section className="card p-5">
            <h2 className="text-base mb-3">Activity timeline</h2>
            {events.length === 0 ? (
              <p className="text-sm text-navy-300 italic">No events logged yet.</p>
            ) : (
              <ol className="space-y-3">
                {events.map((ev) => (
                  <li key={ev.id} className="text-sm border-l-2 border-navy-100 pl-3">
                    <div className="flex items-baseline gap-2">
                      <span className="font-medium text-navy-700">{ev.event_type.replaceAll('_', ' ')}</span>
                      <span className="text-xs text-navy-300">{ev.actor}</span>
                      <span className="text-xs text-navy-300">{new Date(ev.created_at).toLocaleString()}</span>
                    </div>
                    {ev.payload && (
                      <pre className="text-xs text-navy-500 bg-navy-50/60 rounded p-2 mt-1 overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(ev.payload, null, 2)}
                      </pre>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </section>

          {emails.length > 0 && (
            <section className="card p-5">
              <h2 className="text-base mb-3">Email log</h2>
              <div className="space-y-2">
                {emails.map((e) => (
                  <div key={e.id} className="text-sm border border-navy-100 rounded-md p-3">
                    <div className="flex items-center gap-2 text-xs text-navy-400 mb-1">
                      <span className={`badge ${e.direction === 'inbound' ? 'bg-navy-50 text-navy-600' : 'bg-moss-50 text-moss-700'}`}>{e.direction}</span>
                      <span>{e.from_addr} → {e.to_addr}</span>
                      <span>{new Date(e.created_at).toLocaleString()}</span>
                    </div>
                    <div className="font-medium text-navy-700 text-sm">{e.subject}</div>
                    <div className="text-navy-500 text-xs mt-1 whitespace-pre-wrap">{e.body}</div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <div className="space-y-6">
          <section className="card p-5">
            <h2 className="text-base mb-3">Review action</h2>
            <textarea
              className="input mb-2"
              rows={3}
              placeholder="Notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <div className="grid grid-cols-2 gap-2">
              <button className="btn-accent text-xs" disabled={acting} onClick={() => runAction('approve')}>Approve</button>
              <button className="btn-danger text-xs" disabled={acting} onClick={() => runAction('reject')}>Reject</button>
              <button className="btn-outline text-xs" disabled={acting} onClick={() => runAction('escalate')}>Escalate</button>
              <button className="btn-outline text-xs" disabled={acting} onClick={() => runAction('request_info')}>Request info</button>
            </div>
            <button className="btn-ghost text-xs w-full mt-2" disabled={acting} onClick={() => runAction('note')}>Log note only</button>
            {actionMsg && <div className="text-xs text-navy-500 mt-2">{actionMsg}</div>}
          </section>

          <section className="card p-5">
            <h2 className="text-base mb-3">Resume with reply</h2>
            <p className="text-xs text-navy-400 mb-2">Paste the claimant's follow-up email text to re-run it through the pipeline (same as an IMAP reply landing in the inbox).</p>
            <form onSubmit={runResume}>
              <textarea
                className="input mb-2"
                rows={5}
                placeholder="Follow-up email text…"
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
                required
              />
              <button className="btn-primary text-xs w-full" disabled={resuming}>{resuming ? 'Processing…' : 'Run through pipeline'}</button>
            </form>
          </section>

          {reviews.length > 0 && (
            <section className="card p-5">
              <h2 className="text-base mb-3">Review history</h2>
              <ul className="space-y-2 text-xs">
                {reviews.map((r) => (
                  <li key={r.id} className="border-b border-navy-50 pb-2 last:border-0">
                    <div className="font-medium text-navy-700">{r.action} — {r.reviewer_email}</div>
                    {r.notes && <div className="text-navy-500 mt-0.5">{r.notes}</div>}
                    <div className="text-navy-300 mt-0.5">{new Date(r.created_at).toLocaleString()}</div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, mono, block }) {
  return (
    <div className={block ? 'col-span-2' : ''}>
      <div className="text-xs text-navy-400">{label}</div>
      <div className={`text-navy-800 ${mono ? 'font-mono text-xs' : ''} ${block ? 'whitespace-pre-wrap' : ''}`}>
        {value != null && value !== '' ? value : <span className="text-navy-300">—</span>}
      </div>
    </div>
  )
}

function CheckRow({ title, ok, detail }) {
  const icon = ok === true ? '✓' : ok === false ? '✕' : '·'
  const color = ok === true ? 'text-moss-600' : ok === false ? 'text-clay-600' : 'text-navy-300'
  return (
    <div className="flex gap-3">
      <div className={`font-mono ${color} w-4`}>{icon}</div>
      <div>
        <div className="font-medium text-navy-700">{title}</div>
        <div className="text-navy-500 text-xs">{detail}</div>
      </div>
    </div>
  )
}
