import axios from 'axios'
import { useTeacherStore } from '@/stores/teacher'
import { useStudentStore } from '@/stores/student'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
})

apiClient.interceptors.request.use((config) => {
  const teacherToken = useTeacherStore().token
  const studentToken = useStudentStore().token
  const token = teacherToken ?? studentToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default apiClient
