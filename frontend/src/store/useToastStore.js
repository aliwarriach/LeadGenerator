import { create } from 'zustand'

let hideTimer

export const useToastStore = create((set) => ({
  message: null,
  visible: false,
  show: (message) =>
    set(() => {
      clearTimeout(hideTimer)
      hideTimer = setTimeout(() => useToastStore.setState({ visible: false }), 2600)
      return { message, visible: true }
    }),
}))
