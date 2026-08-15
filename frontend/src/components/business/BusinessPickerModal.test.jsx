import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import BusinessPickerModal from './BusinessPickerModal'
import { listLeads } from '../../services/leadsService'
import { createQueryWrapper } from '../../test/queryWrapper'

vi.mock('../../services/leadsService', () => ({
  listLeads: vi.fn(),
}))

const LEADS = [
  { id: 'lead-1', name: 'Best Dental Clinic', category: 'Dental', rating: 4.5, has_website: true },
  { id: 'lead-2', name: 'Downtown Auto Shop', category: 'Automotive', rating: null, has_website: true },
]

beforeEach(() => {
  vi.clearAllMocks()
})

function renderPicker(props = {}) {
  const { Wrapper } = createQueryWrapper()
  return render(
    <Wrapper>
      <BusinessPickerModal open onClose={vi.fn()} activeLeadId={null} onSelect={vi.fn()} {...props} />
    </Wrapper>
  )
}

describe('BusinessPickerModal', () => {
  it('does not render when closed', () => {
    listLeads.mockResolvedValue({ ok: true, data: { items: LEADS, total: 2 } })
    const { Wrapper } = createQueryWrapper()
    render(
      <Wrapper>
        <BusinessPickerModal open={false} onClose={vi.fn()} activeLeadId={null} onSelect={vi.fn()} />
      </Wrapper>
    )
    expect(screen.queryByLabelText('Search businesses')).not.toBeInTheDocument()
  })

  it('lists businesses returned for the default (empty) query', async () => {
    listLeads.mockResolvedValue({ ok: true, data: { items: LEADS, total: 2 } })
    renderPicker()

    await waitFor(() => expect(screen.getByText('Best Dental Clinic')).toBeInTheDocument())
    expect(screen.getByText('Downtown Auto Shop')).toBeInTheDocument()
    expect(listLeads).toHaveBeenCalledWith({ page: 1, page_size: 8 })
  })

  it('debounces typed search and passes it as the name filter', async () => {
    listLeads.mockResolvedValue({ ok: true, data: { items: LEADS, total: 2 } })
    renderPicker()
    await waitFor(() => expect(listLeads).toHaveBeenCalledTimes(1))

    fireEvent.change(screen.getByLabelText('Search businesses'), { target: { value: 'dental' } })

    await waitFor(
      () => expect(listLeads).toHaveBeenLastCalledWith({ name: 'dental', page: 1, page_size: 8 }),
      { timeout: 1000 }
    )
  })

  it('calls onSelect with the lead id when a result is clicked', async () => {
    listLeads.mockResolvedValue({ ok: true, data: { items: LEADS, total: 2 } })
    const onSelect = vi.fn()
    renderPicker({ onSelect })

    await waitFor(() => expect(screen.getByText('Best Dental Clinic')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Best Dental Clinic'))

    expect(onSelect).toHaveBeenCalledWith('lead-1')
  })

  it('marks the currently active lead with a check', async () => {
    listLeads.mockResolvedValue({ ok: true, data: { items: LEADS, total: 2 } })
    renderPicker({ activeLeadId: 'lead-2' })

    await waitFor(() => expect(screen.getByText('Downtown Auto Shop')).toBeInTheDocument())
    const activeRow = screen.getByText('Downtown Auto Shop').closest('button')
    expect(activeRow.className).toMatch(/border-signal/)
  })

  it('shows a no-results message when the search matches nothing', async () => {
    listLeads.mockResolvedValue({ ok: true, data: { items: [], total: 0 } })
    renderPicker()

    await waitFor(() => expect(screen.getByText(/No businesses match/)).toBeInTheDocument())
  })

  it('sorts website-less leads after leads with a website', async () => {
    listLeads.mockResolvedValue({
      ok: true,
      data: {
        total: 2,
        items: [
          { id: 'lead-3', name: 'No Site Co', category: 'Retail', rating: null, has_website: false },
          { id: 'lead-4', name: 'Has Site Co', category: 'Retail', rating: null, has_website: true },
        ],
      },
    })
    renderPicker()

    await waitFor(() => expect(screen.getByText('Has Site Co')).toBeInTheDocument())
    const names = screen.getAllByText(/Co$/).map((el) => el.textContent)
    expect(names).toEqual(['Has Site Co', 'No Site Co'])
    expect(screen.getByText('No site')).toBeInTheDocument()
  })
})
