import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

// App-wide safety net: any render error below this boundary shows a recoverable message
// instead of unmounting the whole React tree (a blank white page).
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="max-w-xl mx-auto my-16 bg-white border border-red-200 rounded-2xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-red-700 mb-2">Something went wrong</h2>
          <p className="text-sm text-slate-600 mb-4">
            An unexpected error occurred while rendering this view. Your data is safe — you can
            try again or start over.
          </p>
          <pre className="text-xs text-slate-500 bg-slate-50 border border-slate-100 rounded-lg p-3 mb-4 overflow-auto max-h-32">
            {this.state.error.message}
          </pre>
          <button
            onClick={() => this.setState({ error: null })}
            className="px-4 py-2 bg-brand text-white rounded-lg text-sm font-medium hover:bg-brand-dark transition-colors"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
