import { create } from 'zustand'

interface UIState {
  // Sidebar
  sidebarOpen: boolean
  sidebarCollapsed: boolean

  // Modals
  transactionModalOpen: boolean
  categoryModalOpen: boolean

  // Filters
  selectedMonth: number
  selectedYear: number

  // Actions
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setSidebarCollapsed: (collapsed: boolean) => void
  setTransactionModalOpen: (open: boolean) => void
  setCategoryModalOpen: (open: boolean) => void
  setSelectedPeriod: (month: number, year: number) => void
}

const currentDate = new Date()

export const useUIStore = create<UIState>((set) => ({
  // Initial state
  sidebarOpen: false,
  sidebarCollapsed: false,
  transactionModalOpen: false,
  categoryModalOpen: false,
  selectedMonth: currentDate.getMonth() + 1,
  selectedYear: currentDate.getFullYear(),

  // Actions
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

  setTransactionModalOpen: (open) => set({ transactionModalOpen: open }),

  setCategoryModalOpen: (open) => set({ categoryModalOpen: open }),

  setSelectedPeriod: (month, year) => set({
    selectedMonth: month,
    selectedYear: year,
  }),
}))
