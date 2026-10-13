import axios from 'axios'
import { API_BASE_URL } from '../config/backend'

const baseURL = API_BASE_URL

const http = axios.create({
  baseURL,
  timeout: 8000,
  headers: {
    'Content-Type': 'application/json'
  }
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => Promise.reject(error)
)

export default http
