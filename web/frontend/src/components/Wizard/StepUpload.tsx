import { useCallback, useState } from 'react'
import { Upload, FileText } from 'lucide-react'

interface Props { onUpload: (file: File) => Promise<void> }

export default function StepUpload({ onUpload }: Props) {
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [filename, setFilename] = useState<string | null>(null)

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.endsWith('.csv')) return
    setFilename(file.name)
    setLoading(true)
    await onUpload(file)
    setLoading(false)
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

      <div className="mt-6 p-4 bg-blue-50 rounded-xl border border-blue-100">
        <p className="text-sm text-blue-700">
          <strong>Tip:</strong> Each row should be one observation. Column headers become variable names.
          Include a group/treatment column if you're comparing groups.
        </p>
      </div>
    </div>
  )
}
