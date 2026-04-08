import axios from 'axios'
import { useTeacherStore } from '@/stores/teacher'
import { useStudentStore } from '@/stores/student'
import { API_BASE_URL } from './config'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
})

apiClient.interceptors.request.use((config) => {
  const url = config.url ?? ''
  const isStudentRoute = url.startsWith('/student') || url.startsWith('/auth/student')
  const token = isStudentRoute
    ? useStudentStore().token
    : (useTeacherStore().token ?? useStudentStore().token)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url ?? ''
      if (url.startsWith('/student')) {
        useStudentStore().logout()
        window.location.href = '/student/join'
      } else {
        useTeacherStore().logout()
        window.location.href = '/teacher'
      }
    }
    return Promise.reject(error)
  },
)

export default apiClient
