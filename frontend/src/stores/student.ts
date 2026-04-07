import { defineStore } from 'pinia'
import { ref } from 'vue'

interface Student {
  id: string
  name: string
  level: number
  streak_count: number
}

const TOKEN_KEY = 'liter_student_token'
const INFO_KEY = 'liter_student_info'

export const useStudentStore = defineStore('student', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const student = ref<Student | null>(
    JSON.parse(localStorage.getItem(INFO_KEY) ?? 'null'),
  )

  function setAuth(newToken: string, newStudent: Student) {
    token.value = newToken
    student.value = newStudent
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(INFO_KEY, JSON.stringify(newStudent))
  }

  function logout() {
    token.value = null
    student.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(INFO_KEY)
  }

  return { token, student, setAuth, logout }
})
