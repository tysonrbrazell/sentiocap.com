'use client'

import { useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { ChevronLeft, Upload, FileText, CheckCircle, Loader } from 'lucide-react'
import { api } from '@/lib/api'
import { formatCurrency, confidenceToSignal, confidenceToLabel } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Table, Thead, Tbody, Tr, Th, Td } from '@/components/ui/Table'

type Phase = 'upload' | 'classifying' | 'review'

export default function PlanUploadPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [phase, setPhase] = useState<Phase>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<import('@/lib/types').UploadPreviewResponse | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)

  const { data: plan } = useQuery({
    queryKey: ['plan', id],
    queryFn: () => api.plans.get(id),
  })

  const { data: jobStatus } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.jobs.status(jobId!),
    enabled: !!jobId && phase === 'classifying',
    refetchInterval: (data) =>
      data?.state.data?.status === 'completed' || data?.state.data?.status === 'failed' ? false : 2000,
  })

  // Job completion
  if (jobStatus?.status === 'completed' && phase === 'classifying') {
    setPhase('review')
  }

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles[0]) setFile(acceptedFiles[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
    },
    maxFiles: 1,
  })

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setError('')

    try {
      const result = await api.plans.uploadFile(id, file)
      setPreview(result)
      // Start classification
      const classifyResult = await api.plans.classify(id)
      setJobId(classifyResult.job_id)
      setPhase('classifying')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <Link href={`/plans/${id}`} className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-brand-primary mb-3">
          <ChevronLeft className="w-4 h-4" />
          Back to {plan?.name || 'Plan'}
        </Link>
        <h1 className="text-xl font-semibold text-brand-primary">Upload & Classify</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Upload a CSV or XLSX file to import line items and classify them with AI
        </p>
      </div>

      {/* Phase 1: Upload */}
      {phase === 'upload' && (
        <Card>
          <CardContent>
            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {error}
              </div>
            )}

            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
                isDragActive
                  ? 'border-brand-accent bg-brand-accent-light'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              <input {...getInputProps()} />
              <Upload className="w-10 h-10 text-gray-300 mx-auto mb-4" />
              {isDragActive ? (
                <p className="text-brand-accent font-medium">Drop your file here</p>
              ) : (
                <>
                  <p className="text-gray-600 font-medium mb-1">Drag & drop your GL export</p>
                  <p className="text-sm text-gray-400">or click to browse — CSV or XLSX accepted</p>
                </>
              )}
            </div>

            {file && (
              <div className="mt-4 flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-brand-primary">{file.name}</p>
                    <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(0)} KB</p>
                  </div>
                </div>
                <Button loading={uploading} onClick={handleUpload}>
                  Classify & Import
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Phase 2: Classifying */}
      {phase === 'classifying' && (
        <Card>
          <CardContent className="text-center py-16">
            <Loader className="w-12 h-12 text-brand-accent mx-auto mb-4 animate-spin" />
            <h3 className="text-base font-semibold text-brand-primary mb-2">
              AI Classification in Progress
            </h3>
            {jobStatus && (
              <>
                <p className="text-sm text-gray-500 mb-4">
                  Classifying {jobStatus.processed_items}/{jobStatus.total_items} line items...
                </p>
                <div className="max-w-xs mx-auto bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-brand-accent h-2 rounded-full transition-all"
                    style={{ width: `${(jobStatus.processed_items / Math.max(jobStatus.total_items, 1)) * 100}%` }}
                  />
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Phase 3: Review */}
      {phase === 'review' && preview && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 px-3 py-2 rounded-lg border border-green-100">
              <CheckCircle className="w-4 h-4" />
              Classification complete — {preview.rows_detected} items classified
            </div>
            <Button onClick={() => router.push(`/plans/${id}`)}>
              View Plan
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Classification Preview (first {preview.preview_count} rows)</CardTitle>
            </CardHeader>
            <Table>
              <Thead>
                <Tr>
                  <Th>#</Th>
                  <Th>Description</Th>
                  <Th>L1</Th>
                  <Th>L2</Th>
                  <Th>L3</Th>
                  <Th>Confidence</Th>
                  <Th className="text-right">Annual Total</Th>
                </Tr>
              </Thead>
              <Tbody>
                {preview.preview.map((row) => {
                  const cls = row.suggested_classification
                  const conf = cls?.confidence
                  const confSignal = conf != null ? confidenceToSignal(conf) : null
                  return (
                    <Tr key={row.row} className={
                      confSignal === 'GREEN' ? 'bg-green-50/30' :
                      confSignal === 'YELLOW' ? 'bg-yellow-50/30' :
                      confSignal === 'RED' ? 'bg-red-50/30' : ''
                    }>
                      <Td className="text-gray-400">{row.row}</Td>
                      <Td className="max-w-sm truncate">{row.source_description}</Td>
                      <Td>
                        {cls?.classified_l1 ? (
                          <Badge variant={cls.classified_l1 === 'RTB' ? 'rtb' : 'ctb'}>
                            {cls.classified_l1}
                          </Badge>
                        ) : '—'}
                      </Td>
                      <Td className="text-xs text-gray-600">{cls?.classified_l2 || '—'}</Td>
                      <Td className="text-xs text-gray-500">{cls?.classified_l3 || '—'}</Td>
                      <Td>
                        {conf != null && confSignal ? (
                          <Badge signal={confSignal}>{confidenceToLabel(conf)}</Badge>
                        ) : '—'}
                      </Td>
                      <Td className="text-right font-medium">
                        {formatCurrency(row.annual_total)}
                      </Td>
                    </Tr>
                  )
                })}
              </Tbody>
            </Table>
          </Card>
        </div>
      )}
    </div>
  )
}
