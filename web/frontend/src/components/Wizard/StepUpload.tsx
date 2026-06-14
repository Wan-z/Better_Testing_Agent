import { useCallback, useState } from 'react'
import { Upload, FileText, FlaskConical } from 'lucide-react'

interface Props { onUpload: (file: File) => Promise<void> }

export default function StepUpload({ onUpload }: Props) {
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [filename, setFilename] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.endsWith('.csv')) {
      setError('Please upload a .csv file.')
      return
    }
    setFilename(file.name)
    setLoading(true)
    setError(null)
    try {
      await onUpload(file)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(
        msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('ECONNREFUSED')
          ? 'Cannot connect to the server. Make sure the backend is running.'
          : msg || 'Upload failed. Please try again.'
      )
      setLoading(false)
    }
  }, [onUpload])

  const handleSampleData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/sample.csv')
      if (!res.ok) throw new Error('Could not load sample data.')
      const blob = await res.blob()
      const file = new File([blob], 'nc_overdose_counties.csv', { type: 'text/csv' })
      setFilename(file.name)
      await onUpload(file)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(
        msg.includes('Failed to fetch') || msg.includes('NetworkError')
          ? 'Cannot connect to the server. Make sure the backend is running.'
          : msg || 'Failed to load sample data.'
      )
      setLoading(false)
    }
  }, [onUpload])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Upload your data</h2>
      <p className="text-slate-500 mb-8">Upload a CSV file. HTA will automatically detect variable types.</p>

      <label
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center justify-center w-full h-56 rounded-2xl border-2 border-dashed cursor-pointer transition-colors ${
          dragging ? 'border-brand bg-indigo-50' : 'border-slate-300 bg-white hover:border-brand hover:bg-indigo-50'
        }`}
      >
        <input
          type="file"
          accept=".csv"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />
        {loading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin" />
            <p className="text-slate-500 text-sm">Profiling data…</p>
          </div>
        ) : filename ? (
          <div className="flex flex-col items-center gap-2">
            <FileText size={36} className="text-brand" />
            <p className="font-medium text-slate-700">{filename}</p>
            <p className="text-sm text-slate-400">Click to replace</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-14 h-14 bg-indigo-50 rounded-xl flex items-center justify-center">
              <Upload size={26} className="text-brand" />
            </div>
            <p className="font-medium text-slate-700">Drop your CSV here, or click to browse</p>
            <p className="text-sm text-slate-400">Accepts .csv files up to 50 MB</p>
          </div>
        )}
      </label>

      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-5 flex items-center gap-3">
        <div className="h-px flex-1 bg-slate-200" />
        <span className="text-xs text-slate-400 shrink-0">or try the built-in sample</span>
        <div className="h-px flex-1 bg-slate-200" />
      </div>

      <button
        onClick={handleSampleData}
        disabled={loading}
        className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-3 bg-white border border-slate-200 text-slate-700 rounded-xl text-sm font-medium hover:bg-slate-50 hover:border-indigo-200 transition-colors disabled:opacity-40"
      >
        <FlaskConical size={15} className="text-brand" />
        Load sample data — NC county overdose rates (100 observations)
      </button>

      <div className="mt-6 p-4 bg-blue-50 rounded-xl border border-blue-100">
        <p className="text-sm text-blue-700">
          <strong>Tip:</strong> Each row should be one observation. Column headers become variable names.
          Include a group/treatment column if you're comparing groups.
        </p>
      </div>
    </div>
  )
}
