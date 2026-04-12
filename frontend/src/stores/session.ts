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

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref<string | null>(null)
  const passage = ref<Passage | null>(null)
  const questions = ref<Question[]>([])
  const currentQuestionIndex = ref(0) // 0-based
  const answers = ref<(number | null)[]>([null, null, null])
  const phase = ref<SessionPhase>('idle')

  // 토의 상태
  const allCorrect = ref<boolean | null>(null)
  const discussionMessages = ref<DiscussionMessage[]>([])
  const scores = ref<SessionScores | null>(null)

  let _msgIdCounter = 0

  function startSession(data: {
    session_id: string
    passage: Passage
    questions: Question[]
  }) {
    sessionId.value = data.session_id
    passage.value = data.passage
    questions.value = data.questions
    currentQuestionIndex.value = 0
    answers.value = [null, null, null]
    phase.value = 'reading'
    allCorrect.value = null
    discussionMessages.value = []
    scores.value = null
    _msgIdCounter = 0
  }

  function goToMcq() {
    phase.value = 'mcq'
  }

  function recordAnswer(questionIndex: number, selectedIndex: number) {
    answers.value[questionIndex] = selectedIndex
  }

  function nextQuestion() {
    if (currentQuestionIndex.value < 2) {
      currentQuestionIndex.value++
    } else {
      phase.value = 'discussion'
    }
  }

  function addDiscussionMessage(msg: Omit<DiscussionMessage, 'id'>) {
    discussionMessages.value.push({ ...msg, id: ++_msgIdCounter })
  }

  function setScores(data: SessionScores) {
    scores.value = data
    phase.value = 'done'
  }

  function reset() {
    sessionId.value = null
    passage.value = null
    questions.value = []
    currentQuestionIndex.value = 0
    answers.value = [null, null, null]
    phase.value = 'idle'
    allCorrect.value = null
    discussionMessages.value = []
    scores.value = null
    _msgIdCounter = 0
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
    reset,
  }
})
