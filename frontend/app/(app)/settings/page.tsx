'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { getStoredUser } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Input, Select } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { Table, Thead, Tbody, Tr, Th, Td } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import { PageSpinner } from '@/components/ui/Spinner'
import { SECTORS } from '@/lib/constants'
import type { OrgUpdate } from '@/lib/types'

const SECTOR_OPTIONS = SECTORS.map((s) => ({ value: s, label: s }))

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin' },
  { value: 'analyst', label: 'Analyst' },
  { value: 'viewer', label: 'Viewer' },
]

export default function SettingsPage() {
  const qc = useQueryClient()
  const user = getStoredUser()
  const orgId = user?.org_id

  const [activeTab, setActiveTab] = useState<'org' | 'users'>('org')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('analyst')
  const [savingOrg, setSavingOrg] = useState(false)
  const [orgSaved, setOrgSaved] = useState(false)

  const { data: org, isLoading } = useQuery({
    queryKey: ['org', orgId],
    queryFn: () => api.organizations.get(orgId!),
    enabled: !!orgId,
  })

  const { data: members } = useQuery({
    queryKey: ['org-members', orgId],
    queryFn: () => api.organizations.members(orgId!),
    enabled: !!orgId,
  })

  const [orgForm, setOrgForm] = useState<OrgUpdate>({})

  // Sync org data when loaded
  if (org && Object.keys(orgForm).length === 0) {
    setOrgForm({
      name: org.name,
      sector: org.sector || '',
      industry: org.industry || '',
      ticker: org.ticker || '',
      revenue: org.revenue,
      employees: org.employees,
      fiscal_year_end: org.fiscal_year_end || '',
    })
  }

  const removeMemberMutation = useMutation({
    mutationFn: (userId: string) => api.organizations.removeMember(orgId!, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['org-members', orgId] }),
  })

  const inviteMutation = useMutation({
    mutationFn: () => api.organizations.inviteMember(orgId!, { email: inviteEmail, role: inviteRole }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['org-members', orgId] })
      setInviteEmail('')
    },
  })

  async function handleSaveOrg(e: React.FormEvent) {
    e.preventDefault()
    setSavingOrg(true)
    try {
      await api.organizations.update(orgId!, orgForm)
      setOrgSaved(true)
      setTimeout(() => setOrgSaved(false), 2000)
    } finally {
      setSavingOrg(false)
    }
  }

  if (isLoading) return <PageSpinner />

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-brand-primary">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">Manage your organization and team</p>
      </div>

      {/* Tab nav */}
      <div className="flex border-b border-gray-200 gap-4">
        {(['org', 'users'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-3 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'text-brand-accent border-brand-accent'
                : 'text-gray-500 border-transparent hover:text-brand-primary'
            }`}
          >
            {tab === 'org' ? 'Organization' : 'Team Members'}
          </button>
        ))}
      </div>

      {/* Org Profile */}
      {activeTab === 'org' && (
        <Card>
          <CardHeader>
            <CardTitle>Organization Profile</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSaveOrg} className="space-y-4 max-w-lg">
              <Input
                label="Organization Name"
                value={orgForm.name || ''}
                onChange={(e) => setOrgForm((prev) => ({ ...prev, name: e.target.value }))}
              />
              <div className="grid grid-cols-2 gap-4">
                <Select
                  label="Sector"
                  value={orgForm.sector || ''}
                  onChange={(e) => setOrgForm((prev) => ({ ...prev, sector: e.target.value }))}
                  options={SECTOR_OPTIONS}
                  placeholder="Select sector..."
                />
                <Input
                  label="Industry"
                  value={orgForm.industry || ''}
                  onChange={(e) => setOrgForm((prev) => ({ ...prev, industry: e.target.value }))}
                  placeholder="e.g. Enterprise Software"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Ticker Symbol"
                  value={orgForm.ticker || ''}
                  onChange={(e) => setOrgForm((prev) => ({ ...prev, ticker: e.target.value }))}
                  placeholder="e.g. MSFT"
                />
                <Input
                  label="Annual Revenue ($)"
                  type="number"
                  value={orgForm.revenue || ''}
                  onChange={(e) => setOrgForm((prev) => ({ ...prev, revenue: parseFloat(e.target.value) }))}
                  placeholder="0"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Employees"
                  type="number"
                  value={orgForm.employees || ''}
                  onChange={(e) => setOrgForm((prev) => ({ ...prev, employees: parseInt(e.target.value) }))}
                  placeholder="0"
                />
                <Input
                  label="Fiscal Year End"
                  value={orgForm.fiscal_year_end || ''}
                  onChange={(e) => setOrgForm((prev) => ({ ...prev, fiscal_year_end: e.target.value }))}
                  placeholder="e.g. Dec-31"
                />
              </div>
              <Button type="submit" loading={savingOrg}>
                {orgSaved ? '✓ Saved!' : 'Save Changes'}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Users */}
      {activeTab === 'users' && (
        <div className="space-y-4">
          {/* Invite */}
          <Card>
            <CardHeader>
              <CardTitle>Invite Team Member</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-3">
                <Input
                  placeholder="colleague@company.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="flex-1"
                />
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-accent"
                >
                  {ROLE_OPTIONS.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
                <Button
                  loading={inviteMutation.isPending}
                  onClick={() => inviteEmail && inviteMutation.mutate()}
                >
                  <Plus className="w-4 h-4" />
                  Invite
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Members table */}
          <Card>
            <CardHeader>
              <CardTitle>Team Members ({members?.length ?? 0})</CardTitle>
            </CardHeader>
            <Table>
              <Thead>
                <Tr>
                  <Th>Name</Th>
                  <Th>Email</Th>
                  <Th>Role</Th>
                  <Th></Th>
                </Tr>
              </Thead>
              <Tbody>
                {(members ?? []).map((m) => (
                  <Tr key={m.id}>
                    <Td className="font-medium">{m.name}</Td>
                    <Td className="text-gray-500">{m.email}</Td>
                    <Td>
                      <Badge variant={m.role === 'admin' ? 'blue' : m.role === 'analyst' ? 'emerald' : 'gray'}>
                        {m.role}
                      </Badge>
                    </Td>
                    <Td>
                      {m.id !== user?.id && (
                        <button
                          onClick={() => {
                            if (confirm(`Remove ${m.name}?`)) removeMemberMutation.mutate(m.id)
                          }}
                          className="text-gray-300 hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Card>
        </div>
      )}
    </div>
  )
}
