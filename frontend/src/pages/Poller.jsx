import { useEffect, useState } from 'react'
import api, { errMsg } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Poller() {
  const { isManagerOrAdmin } = useAuth()
  const [status, setStatus] = useState(null)
  const [history, setHistory] = useState([])
  const [interval, setIntervalVal] = useState(60)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const load = async () => {
    try {
      const [s, h] = await Promise.all([api.get('/poller/status'), api.get('/poller/history')])
      setStatus(s.data)
      setHistory(h.data)
    } catch (err) {
      setMsg(errMsg(err))
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [])

  const start = async () => {
    setBusy(true)
    try {
      await api.post('/poller/start', null, { params: { interval_seconds: interval } })
      await load()
    } catch (err) { setMsg(errMsg(err)) } finally { setBusy(false) }
  }

  const stop = async () => {
    setBusy(true)
    try {
      await api.post('/poller/stop')
      await load()
    } catch (err) { setMsg(errMsg(err)) } finally { setBusy(false) }
  }

  const pollNow = async () => {
    setBusy(true)
    setMsg('')
    try {
      const res = await api.post('/poller/poll-now')
      setMsg(`Processed ${res.data.claims_processed} claim(s).`)
      await load()
    } catch (err) { setMsg(errMsg(err, 'Poll failed — check IMAP settings.')) } finally { setBusy(false) }
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl mb-1">Inbox poller</h1>
      <p className="text-sm text-navy-400 mb-6">
        Checks the configured IMAP inbox for new claim emails and replies, and runs each one
        through the pipeline automatically. Configure IMAP credentials on the Settings page first.
      </p>

      <div className="card p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-sm font-medium text-navy-700">
              Status: <span className={status?.running ? 'text-moss-600' : 'text-navy-400'}>{status?.running ? 'Running' : 'Stopped'}</span>
            </div>
            {status?.next_run_at && <div className="text-xs text-navy-400">Next run: {new Date(status.next_run_at).toLocaleString()}</div>}
            {status?.last_run_at && <div className="text-xs text-navy-400">Last run: {new Date(status.last_run_at).toLocaleString()} — {status.last_result}</div>}
            {status?.last_error && <div className="text-xs text-clay-600 mt-1">Last error: {status.last_error}</div>}
          </div>
        </div>

        {isManagerOrAdmin && (
          <div className="flex items-center gap-2 mb-3">
            <label className="text-xs text-navy-500">Poll every</label>
            <input className="input w-24" type="number" min={10} value={interval} onChange={(e) => setIntervalVal(e.target.value)} />
            <span className="text-xs text-navy-500">seconds</span>
          </div>
        )}

        <div className="flex gap-2">
          {isManagerOrAdmin && !status?.running && <button className="btn-accent text-sm" disabled={busy} onClick={start}>Start polling</button>}
          {isManagerOrAdmin && status?.running && <button className="btn-danger text-sm" disabled={busy} onClick={stop}>Stop polling</button>}
          <button className="btn-outline text-sm" disabled={busy} onClick={pollNow}>Poll now</button>
        </div>
        {msg && <div className="text-xs text-navy-500 mt-3">{msg}</div>}
      </div>

      <h2 className="text-lg mb-3">Run history</h2>
      <div className="card overflow-hidden">
        <table className="table-shell">
          <thead>
            <tr><th>Started</th><th>Finished</th><th>Emails processed</th><th>Status</th><th>Error</th></tr>
          </thead>
          <tbody>
            {history.length === 0 && <tr><td colSpan={5} className="text-center text-navy-400 py-6">No poll runs yet.</td></tr>}
            {history.map((r) => (
              <tr key={r.id}>
                <td className="text-xs">{new Date(r.started_at).toLocaleString()}</td>
                <td className="text-xs">{r.finished_at ? new Date(r.finished_at).toLocaleString() : '—'}</td>
                <td className="text-xs">{r.claims_processed ?? '—'}</td>
                <td className="text-xs">{r.status}</td>
                <td className="text-xs text-clay-600">{r.error || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
