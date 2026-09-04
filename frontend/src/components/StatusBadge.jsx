const STATUS_STYLES = {
  new: 'bg-navy-50 text-navy-600',
  awaiting_info: 'bg-wheat/20 text-navy-700 border border-wheat/60',
  needs_manual_followup: 'bg-clay-50 text-clay-700 border border-clay-200',
  escalate_to_manager: 'bg-clay-50 text-clay-700 border border-clay-200',
  rejected_unknown_policy: 'bg-clay-100 text-clay-800 border border-clay-300',
  auto_approve: 'bg-moss-50 text-moss-700 border border-moss-200',
  manager_approved: 'bg-moss-50 text-moss-700 border border-moss-200',
  manager_rejected: 'bg-clay-50 text-clay-700 border border-clay-200',
  superseded: 'bg-navy-50 text-navy-400 border border-navy-100 line-through',
}

const STATUS_LABELS = {
  new: 'New',
  awaiting_info: 'Awaiting info',
  needs_manual_followup: 'Needs manual follow-up',
  escalate_to_manager: 'Escalated',
  rejected_unknown_policy: 'Unknown policy',
  auto_approve: 'Auto-approved',
  manager_approved: 'Approved',
  manager_rejected: 'Rejected',
  superseded: 'Superseded',
}

export default function StatusBadge({ status }) {
  const cls = STATUS_STYLES[status] || 'bg-navy-50 text-navy-500 border border-navy-100'
  const label = STATUS_LABELS[status] || status || 'Unknown'
  return <span className={`badge ${cls}`}>{label}</span>
}
