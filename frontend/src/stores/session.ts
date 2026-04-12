import { defineStore } from 'pinia'
import { ref } from 'vue'

interface Passage {
  title: string
  genre: string
  difficulty: number
  content: string
}

interface Question {
  index: number
  type: 'info' | 'reasoning' | 'vocabulary'
  text: string
  choices: string[]
}

export interface DiscussionMessage {
  id: number
  speaker: 'moderator' | 'peer_a' | 'peer_b' | 'user'
  content: string
  round: number
}

export interface SessionScores {
  score_reasoning: number
  score_vocabulary: number
  score_context: number
  feedback: string
  streak_count: number
  question_results: QuestionResult[]
}

export interface QuestionResult {
  question_index: number
  question_type: string
  question_text: string
  choices: string[]
  correct_index: number
  selected_index: number | null
  is_correct: boolean | null
}

export type SessionPhase = 'idle' | 'reading' | 'mcq' | 'discussion' | 'done'

interface PersistedSessionState {
  sessionId: string | null
  passage: Passage | null
  questions: Question[]
  currentQuestionIndex: number
  answers: (number | null)[]
  phase: SessionPhase
  allCorrect: boolean | null
  discussionMessages: DiscussionMessage[]
  scores: SessionScores | null
}

const STORAGE_KEY = 'liter_session_state'

function loadPersistedState(): PersistedSessionState | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null

  try {
    return JSON.parse(raw) as PersistedSessionState
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return null
  }
}

export const useSessionStore = defineStore('session', () => {
  const persisted = loadPersistedState()

  const sessionId = ref<string | null>(persisted?.sessionId ?? null)
  const passage = ref<Passage | null>(persisted?.passage ?? null)
  const questions = ref<Question[]>(persisted?.questions ?? [])
  const currentQuestionIndex = ref(persisted?.currentQuestionIndex ?? 0)
  const answers = ref<(number | null)[]>(
    persisted?.answers ?? [],
  )
  const phase = ref<SessionPhase>(persisted?.phase ?? 'idle')

  // 토의 상태
  const allCorrect = ref<boolean | null>(persisted?.allCorrect ?? null)
  const discussionMessages = ref<DiscussionMessage[]>(
    persisted?.discussionMessages ?? [],
  )
  const scores = ref<SessionScores | null>(persisted?.scores ?? null)

  let _msgIdCounter = 0

  function persist() {
    if (!sessionId.value || phase.value === 'idle') {
      localStorage.removeItem(STORAGE_KEY)
      return
    }

    const state: PersistedSessionState = {
      sessionId: sessionId.value,
      passage: passage.value,
      questions: questions.value,
      currentQuestionIndex: currentQuestionIndex.value,
      answers: answers.value,
      phase: phase.value,
      allCorrect: allCorrect.value,
      discussionMessages: discussionMessages.value,
      scores: scores.value,
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }

  function startSession(data: {
    session_id: string
    passage: Passage
    questions: Question[]
  }) {
    sessionId.value = data.session_id
    passage.value = data.passage
    questions.value = data.questions
    currentQuestionIndex.value = 0
    answers.value = Array.from({ length: data.questions.length }, () => null)
    phase.value = 'reading'
    allCorrect.value = null
    discussionMessages.value = []
    scores.value = null
    _msgIdCounter = 0
    persist()
  }

  function goToMcq() {
    phase.value = 'mcq'
    persist()
  }

  function recordAnswer(questionIndex: number, selectedIndex: number) {
    const index = questionIndex - 1
    if (index < 0 || index >= answers.value.length) return
    answers.value[index] = selectedIndex
    persist()
  }

  function nextQuestion() {
    if (currentQuestionIndex.value < questions.value.length - 1) {
      currentQuestionIndex.value++
    } else {
      phase.value = 'discussion'
    }
    persist()
  }

  function addDiscussionMessage(msg: Omit<DiscussionMessage, 'id'>) {
    discussionMessages.value.push({ ...msg, id: ++_msgIdCounter })
    persist()
  }

  function setScores(data: SessionScores) {
    scores.value = data
    phase.value = 'done'
    persist()
  }

  function reset() {
    sessionId.value = null
    passage.value = null
    questions.value = []
    currentQuestionIndex.value = 0
    answers.value = []
    phase.value = 'idle'
    allCorrect.value = null
    discussionMessages.value = []
    scores.value = null
    _msgIdCounter = 0
    localStorage.removeItem(STORAGE_KEY)
  }

  function setPhase(nextPhase: SessionPhase) {
    phase.value = nextPhase
    persist()
  }

  function hasActiveSession() {
    return Boolean(sessionId.value && phase.value !== 'idle' && phase.value !== 'done')
  }

  return {
    sessionId,
    passage,
    questions,
    currentQuestionIndex,
    answers,
    phase,
    allCorrect,
    discussionMessages,
    scores,
    startSession,
    goToMcq,
    recordAnswer,
    nextQuestion,
    addDiscussionMessage,
    setScores,
    setPhase,
    hasActiveSession,
    reset,
  }
})
