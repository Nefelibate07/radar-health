import { ref } from 'vue'

export const faultDetailVisible = ref(false)
export const currentFaultData = ref(null)

export function openFaultDetail(data) {
  currentFaultData.value = data
  faultDetailVisible.value = true
}

export function closeFaultDetail() {
  faultDetailVisible.value = false
  currentFaultData.value = null
}
