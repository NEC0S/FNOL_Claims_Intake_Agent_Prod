import { useEffect, useState } from 'react'
import api, { errMsg } from '../api/client'

export default function Settings() {
  const [settings, setSettings] = useState(null)
  const [form, setForm] = useState({})
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState('')
  const [testResults, setTestResults] = useState({})
  const [testing, setTesting] = useState({})

  const load = async () => {
    try {
      const res = await api.get('/settings')
      setSettings(res.data)
    } catch (err) {
      setError(errMsg(err, 'Could not load settings.'))
    }
  }

  useEffect(() => { load() }, [])

  const setField = (key, value) => setForm((p) => ({ ...p, [key]: value }))

  const save = async () => {
    setSaving(true)
    setSavedMsg('')
    setError('')
    try {
      const res = await api.put('/settings', { values: form })
      setSettings(res.data.settings)
      setForm({})
      setSavedMsg('Saved. New values take effect immediately, no restart needed.')
    } catch (err) {
      setError(errMsg(err, 'Could not save settings.'))
    } finally {
      setSaving(false)
    }
  }

  const test = async (kind) => {
    setTesting((p) => ({ ...p, [kind]: true }))
    try {
      const res = await api.post(`/settings/test/${kind}`)
      setTestResults((p) => ({ ...p, [kind]: res.data }))
    } catch (err) {
      setTestResults((p) => ({ ...p, [kind]: { ok: false, detail: errMsg(err) } }))
    } finally {
      setTesting((p) => ({ ...p, [kind]: false }))
    }
  }

  if (!settings) return <div className="text-navy-400 text-sm">{error || 'Loading…'}</div>

  const src = settings._source || {}

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl mb-1">Settings</h1>
      <p className="text-sm text-navy-400 mb-6">
        Configure API keys and mail credentials here. Anything you leave blank falls back to
        the values in the backend's .env file — you don't have to fill in everything.
      </p>

      {error && <div className="text-sm text-clay-600 bg-clay-50 border border-clay-200 rounded-md px-3 py-2 mb-4">{error}</div>}
      {savedMsg && <div className="text-sm text-moss-700 bg-moss-50 border border-moss-200 rounded-md px-3 py-2 mb-4">{savedMsg}</div>}

      <SectionCard
        title="LLM / Google API"
        subtitle="Used by the extraction, follow-up, risk-scoring, and report-writing agents."
        onTest={() => test('llm')}
        testing={testing.llm}
        testResult={testResults.llm}
      >
        <SourceNote k="llm_api_key" src={src} />
        <TextField label="Google / LLM API key" placeholder={settings.llm_api_key || 'not set'} onChange={(v) => setField('llm_api_key', v)} type="password" />
        <TextField label="LLM base URL (OpenAI-compatible)" placeholder={settings.llm_base_url} onChange={(v) => setField('llm_base_url', v)} />
        <TextField label="Model" placeholder={settings.llm_model} onChange={(v) => setField('llm_model', v)} />
      </SectionCard>

      <SectionCard
        title="SMTP (outbound email)"
        subtitle="Sends follow-up requests to claimants for missing information."
        onTest={() => test('smtp')}
        testing={testing.smtp}
        testResult={testResults.smtp}
      >
        <SourceNote k="smtp_user" src={src} />
        <TextField label="SMTP host" placeholder={settings.smtp_host} onChange={(v) => setField('smtp_host', v)} />
        <TextField label="SMTP port" placeholder={String(settings.smtp_port)} onChange={(v) => setField('smtp_port', v)} type="number" />
        <TextField label="SMTP username / email" placeholder={settings.smtp_user || 'not set'} onChange={(v) => setField('smtp_user', v)} />
        <TextField label="SMTP password (app password)" placeholder={settings.smtp_password || 'not set'} onChange={(v) => setField('smtp_password', v)} type="password" />
      </SectionCard>

      <SectionCard
        title="IMAP (inbound email)"
        subtitle="Reads the claims mailbox for new FNOL emails and claimant replies."
        onTest={() => test('imap')}
        testing={testing.imap}
        testResult={testResults.imap}
      >
        <SourceNote k="imap_user" src={src} />
        <TextField label="IMAP host" placeholder={settings.imap_host} onChange={(v) => setField('imap_host', v)} />
        <TextField label="IMAP port" placeholder={String(settings.imap_port)} onChange={(v) => setField('imap_port', v)} type="number" />
        <TextField label="IMAP username / email" placeholder={settings.imap_user || 'not set'} onChange={(v) => setField('imap_user', v)} />
        <TextField label="IMAP password (app password)" placeholder={settings.imap_password || 'not set'} onChange={(v) => setField('imap_password', v)} type="password" />
        <TextField label="Mailbox" placeholder={settings.imap_mailbox} onChange={(v) => setField('imap_mailbox', v)} />
      </SectionCard>

      <SectionCard title="Business thresholds" subtitle="Change how the decision agent routes claims — no restart needed.">
        <TextField label="Auto-approve payout limit ($)" placeholder={String(settings.auto_approve_payout_limit)} onChange={(v) => setField('auto_approve_payout_limit', v)} type="number" />
        <TextField label="Risk-score escalation threshold (0–1)" placeholder={String(settings.risk_score_escalate_threshold)} onChange={(v) => setField('risk_score_escalate_threshold', v)} type="number" step="0.01" />
        <TextField label="Max follow-up attempts" placeholder={String(settings.max_followup_attempts)} onChange={(v) => setField('max_followup_attempts', v)} type="number" />
        <TextField label="Poll interval (seconds)" placeholder={String(settings.poll_interval_seconds)} onChange={(v) => setField('poll_interval_seconds', v)} type="number" />
      </SectionCard>

      <button className="btn-accent" disabled={saving || Object.keys(form).length === 0} onClick={save}>
        {saving ? 'Saving…' : 'Save changes'}
      </button>
    </div>
  )
}

function SourceNote({ k, src }) {
  const source = src[k]
  if (!source) return null
  return (
    <div className="text-xs text-navy-400 -mt-1 mb-1">
      Currently using: <span className={source === 'ui' ? 'text-moss-600' : 'text-wheat font-medium'}>{source === 'ui' ? 'value saved here' : '.env fallback'}</span>
    </div>
  )
}

function SectionCard({ title, subtitle, children, onTest, testing, testResult }) {
  return (
    <div className="card p-5 mb-5">
      <div className="flex items-start justify-between mb-1">
        <h2 className="text-base">{title}</h2>
        {onTest && (
          <button className="btn-outline text-xs" onClick={onTest} disabled={testing}>
            {testing ? 'Testing…' : 'Test connection'}
          </button>
        )}
      </div>
      {subtitle && <p className="text-xs text-navy-400 mb-4">{subtitle}</p>}
      {testResult && (
        <div className={`text-xs rounded-md px-3 py-2 mb-3 ${testResult.ok ? 'bg-moss-50 text-moss-700 border border-moss-200' : 'bg-clay-50 text-clay-700 border border-clay-200'}`}>
          {testResult.detail}
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">{children}</div>
    </div>
  )
}

function TextField({ label, placeholder, onChange, type = 'text', step }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input className="input" type={type} step={step} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}
