import { defineStore } from 'pinia'
import { ref } from 'vue'

interface Teacher {
  id: string
  email: string
  name: string
}

const TOKEN_KEY = 'liter_teacher_token'
const INFO_KEY = 'liter_teacher_info'

export const useTeacherStore = defineStore('teacher', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const teacher = ref<Teacher | null>(
    JSON.parse(localStorage.getItem(INFO_KEY) ?? 'null'),
  )

  function setAuth(newToken: string, newTeacher: Teacher) {
    token.value = newToken
    teacher.value = newTeacher
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(INFO_KEY, JSON.stringify(newTeacher))
  }

  function logout() {
    token.value = null
    teacher.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(INFO_KEY)
  }

  return { token, teacher, setAuth, logout }
})
