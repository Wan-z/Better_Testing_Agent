import { clsx } from 'clsx'
import type { AssumptionStatus, CaveatSeverity } from '../../types/api'

const assumptionColours: Record<AssumptionStatus, string> = {
  MET:        'bg-green-100 text-green-800',
  VIOLATED:   'bg-red-100 text-red-800',
  MARGINAL:   'bg-amber-100 text-amber-800',
  UNTESTABLE: 'bg-slate-100 text-slate-600',
}

const caveatColours: Record<CaveatSeverity, string> = {
  CRITICAL: 'bg-red-100 text-red-800',
  WARNING:  'bg-amber-100 text-amber-800',
  INFO:     'bg-blue-100 text-blue-800',
}

const assumptionIcons: Record<AssumptionStatus, string> = {
  MET: '✓', VIOLATED: '✗', MARGINAL: '~', UNTESTABLE: '?',
}

export function AssumptionBadge({ status }: { status: AssumptionStatus }) {
  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', assumptionColours[status])}>
      {assumptionIcons[status]} {status}
    </span>
  )
}

export function CaveatBadge({ severity }: { severity: CaveatSeverity }) {
  const icons = { CRITICAL: '🔴', WARNING: '⚠️', INFO: 'ℹ️' }
  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold', caveatColours[severity])}>
      {icons[severity]} {severity}
    </span>
  )
}

export function SignificanceBadge({ significant }: { significant: boolean }) {
  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold',
      significant ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-600',
    )}>
      {significant ? '● Significant' : '● Not significant'}
    </span>
  )
}
