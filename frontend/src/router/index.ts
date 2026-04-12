import { createRouter, createWebHistory } from 'vue-router'
import { useTeacherStore } from '@/stores/teacher'
import { useStudentStore } from '@/stores/student'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: () => import('@/pages/LandingPage.vue'),
      meta: { order: 0 },
    },
    {
      path: '/teacher',
      component: () => import('@/pages/teacher/TeacherAuthPage.vue'),
      meta: { order: 1 },
    },
    {
      path: '/teacher/classrooms',
      component: () => import('@/pages/teacher/TeacherClassroomsPage.vue'),
      meta: { requiresTeacherAuth: true, order: 2 },
    },
    {
      path: '/teacher/dashboard/:classroomId',
      component: () => import('@/pages/TeacherDashboardPage.vue'),
      meta: { requiresTeacherAuth: true, order: 3 },
    },
    {
      path: '/student/join',
      component: () => import('@/pages/StudentOnboarding.vue'),
      meta: { order: 1 },
    },
    {
      path: '/student/home',
      component: () => import('@/pages/StudentHome.vue'),
      meta: { requiresStudentAuth: true, order: 2 },
    },
    {
      path: '/student/session',
      component: () => import('@/pages/StudentSession.vue'),
      meta: { requiresStudentAuth: true, order: 3 },
    },
    {
      path: '/student/discussion',
      component: () => import('@/pages/StudentDiscussion.vue'),
      meta: { requiresStudentAuth: true, order: 4 },
    },
    {
      path: '/student/result',
      component: () => import('@/pages/StudentResult.vue'),
      meta: { requiresStudentAuth: true, order: 5 },
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
