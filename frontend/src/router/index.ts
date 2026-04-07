import { createRouter, createWebHistory } from 'vue-router'
import { useTeacherStore } from '@/stores/teacher'
import { useStudentStore } from '@/stores/student'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: () => import('@/pages/LandingPage.vue'),
    },
    {
      path: '/teacher',
      component: () => import('@/pages/TeacherAuthPage.vue'),
    },
    {
      path: '/teacher/classrooms',
      component: () => import('@/pages/TeacherClassroomsPage.vue'),
      meta: { requiresTeacherAuth: true },
    },
    {
      path: '/teacher/dashboard/:classroomId',
      component: () => import('@/pages/TeacherDashboardPage.vue'),
      meta: { requiresTeacherAuth: true },
    },
    {
      path: '/student/join',
      component: () => import('@/pages/StudentOnboarding.vue'),
    },
    {
      path: '/student/home',
      component: () => import('@/pages/StudentHome.vue'),
      meta: { requiresStudentAuth: true },
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresTeacherAuth) {
    const { token } = useTeacherStore()
    if (!token) return { path: '/teacher' }
  }

  if (to.meta.requiresStudentAuth) {
    const { token } = useStudentStore()
    if (!token) return { path: '/student/join' }
  }
})

export default router
