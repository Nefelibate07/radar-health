import http from './http'

export const getDataProcessing = () => http.get('/api/data-processing')
export const saveDataProcessing = (config) => http.put('/api/data-processing/config', config)
export const getFaultDiagnosis = () => http.get('/api/fault-diagnosis')
