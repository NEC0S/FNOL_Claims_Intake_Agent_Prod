import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { errMsg } from '../api/client'

export default function NewClaim() {
  const navigate = useNavigate()
  const [claimantEmail, setClaimantEmail] = useState('')
  const [rawText, setRawText] = useState('')
  const [damageEstimate, setDamageEstimate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/claims', {
        raw_email_text: rawText,
        claimant_email: claimantEmail,
        damage_estimate: damageEstimate ? parseFloat(damageEstimate) : 0.0,
        source: 'manual',
      })
      navigate(`/claims/${res.data.claim_id}`)
    } catch (err) {
      setError(errMsg(err, 'Could not create claim.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl mb-1">New claim</h1>
      <p className="text-sm text-navy-400 mb-6">
        Paste the claimant's report as free text — the extraction agent will pull out the
        policy number, incident date, location, and description automatically, exactly like
        an inbound FNOL email.
      </p>

      <form onSubmit={handleSubmit} className="card p-6 space-y-4">
        <div>
          <label className="label">Claimant email</label>
          <input className="input" type="email" required value={claimantEmail} onChange={(e) => setClaimantEmail(e.target.value)} />
        </div>
        <div>
          <label className="label">Damage estimate (USD, optional)</label>
          <input className="input" type="number" step="0.01" value={damageEstimate} onChange={(e) => setDamageEstimate(e.target.value)} />
        </div>
        <div>
          <label className="label">Claim report (free text)</label>
          <textarea
            className="input"
            rows={10}
            required
            placeholder={'Example:\n\nMy policy is POL-10293. On 2026-03-14 a hailstorm damaged my car\'s windshield and hood while parked outside my home at 44 Birch Lane, Springfield. Not my fault — it was weather damage.'}
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
          />
        </div>
        {error && <div className="text-sm text-clay-600 bg-clay-50 border border-clay-200 rounded-md px-3 py-2">{error}</div>}
        <button className="btn-accent" disabled={loading}>{loading ? 'Running pipeline…' : 'Submit claim'}</button>
      </form>
    </div>
  )
}
