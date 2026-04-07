export const MOCK_STUDENT_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdHUtMDAxIiwidHlwZSI6InN0dWRlbnQiLCJleHAiOjk5OTk5OTk5OTl9.fake'
export const MOCK_TEACHER_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZWEtMDAxIiwiZXhwIjo5OTk5OTk5OTk5fQ.fake'

export const MOCK_STUDENT_INFO = {
  id: 'stu-001',
  name: '테스트학생',
  level: 2,
  streak_count: 3,
}

export const MOCK_TEACHER_INFO = {
  id: 'tea-001',
  email: 'test@school.edu',
  name: '테스트선생',
}

export const MOCK_JOIN_RESPONSE = {
  student_id: 'stu-001',
  access_token: MOCK_STUDENT_TOKEN,
}

export const MOCK_ME_RESPONSE = {
  name: '테스트학생',
  level: 2,
  streak_count: 3,
  today_session_count: 0,
  classroom_name: '5학년 2반',
  weak_areas: ['reasoning'],
  recent_average_score: 7.4,
  weekly_completed_count: 4,
  total_completed_count: 19,
}

export const MOCK_SESSION_RESPONSE = {
  session_id: 'ses-001',
  passage: {
    title: '광합성의 비밀',
    genre: '과학',
    difficulty: 2,
    content:
      '식물은 햇빛을 이용해 양분을 만든다. 이 과정을 광합성이라고 한다. 잎 속에 있는 엽록체가 햇빛 에너지를 흡수하여 이산화탄소와 물을 포도당으로 변환한다. 이 과정에서 산소가 발생하여 공기 중으로 방출된다.',
  },
  questions: [
    {
      index: 1,
      type: 'info',
      text: '광합성이 일어나는 장소는 어디인가?',
      choices: ['줄기', '뿌리', '잎'],
    },
    {
      index: 2,
      type: 'reasoning',
      text: '햇빛이 없으면 식물은 어떻게 될까?',
      choices: ['광합성이 더 활발해진다', '광합성을 할 수 없다', '물을 더 많이 흡수한다'],
    },
    {
      index: 3,
      type: 'vocabulary',
      text: '"엽록체"의 의미로 가장 적절한 것은?',
      choices: ['뿌리의 일부분', '잎에 있는 세포 소기관', '햇빛의 종류'],
    },
  ],
}

export const MOCK_ANSWER_RESPONSE = { ok: true }

// SSE 스트림 — 첫 번째 호출(빈 content): moderator→peer_a→next_speaker:user
export const MOCK_SSE_ROUND1 = [
  'data: {"speaker":"moderator","content":"오늘 지문에서 광합성에 대해 배웠는데, 가장 흥미로웠던 부분이 무엇인가요?","round":1}\n\n',
  'data: {"speaker":"peer_a","content":"저는 엽록체가 공장처럼 일한다는 게 신기했어요!","round":1}\n\n',
  'data: {"next_speaker":"user","round":1,"is_final":false}\n\n',
].join('')

// SSE 스트림 — 두 번째 호출(사용자 입력 후): peer_b→is_final
export const MOCK_SSE_ROUND2_FINAL = [
  'data: {"speaker":"peer_b","content":"맞아요, 식물도 에너지가 필요하다니 재밌네요.","round":2}\n\n',
  'data: {"speaker":"moderator","content":"좋은 의견들이네요. 오늘 토의 수고했어요!","round":2}\n\n',
  'data: {"is_final":true}\n\n',
].join('')

// 테스트를 단순화할 때 사용 — 한 번의 SSE 호출로 바로 완료
export const MOCK_SSE_QUICK_FINAL = [
  'data: {"speaker":"moderator","content":"오늘 광합성에 대해 잘 공부했어요. 수고했습니다!","round":1}\n\n',
  'data: {"is_final":true}\n\n',
].join('')

export const MOCK_END_SESSION_RESPONSE = {
  score_reasoning: 7.5,
  score_vocabulary: 8.0,
  score_context: 6.5,
  feedback: '오늘 광합성에 대해 깊이 생각해줬어요! 다음에도 이렇게 열심히 참여해 주세요.',
  streak_count: 4,
  question_results: [
    {
      question_index: 1,
      question_type: 'info',
      question_text: '광합성이 일어나는 장소는 어디인가?',
      choices: ['줄기', '뿌리', '잎'],
      correct_index: 2,
      selected_index: 2,
      is_correct: true,
    },
    {
      question_index: 2,
      question_type: 'reasoning',
      question_text: '햇빛이 없으면 식물은 어떻게 될까?',
      choices: ['광합성이 더 활발해진다', '광합성을 할 수 없다', '물을 더 많이 흡수한다'],
      correct_index: 1,
      selected_index: 1,
      is_correct: true,
    },
    {
      question_index: 3,
      question_type: 'vocabulary',
      question_text: '"엽록체"의 의미로 가장 적절한 것은?',
      choices: ['뿌리의 일부분', '잎에 있는 세포 소기관', '햇빛의 종류'],
      correct_index: 1,
      selected_index: 0,
      is_correct: false,
    },
  ],
}

export const MOCK_TEACHER_CLASSROOMS = [
  { id: 'cls-001', name: '5학년 2반', join_code: 'ABC123', student_count: 12 },
]

export const MOCK_CLASSROOM_CREATE_RESPONSE = {
  id: 'cls-002',
  join_code: 'XYZ999',
}

export const MOCK_DASHBOARD_RESPONSE = {
  classroom_name: '5학년 2반',
  summary: {
    total_students: 2,
    active_today: 1,
    completed_today: 1,
    average_recent_score: 5.9,
    average_streak: 2.0,
    attention_count: 1,
  },
  weak_area_summary: [
    { area: 'reasoning', count: 2 },
    { area: 'vocabulary', count: 1 },
  ],
  students: [
    {
      id: 'stu-001',
      name: '김민준',
      level: 2,
      teacher_override_level: null,
      weak_areas: ['reasoning'],
      streak_count: 3,
      recent_avg: 7.2,
      needs_attention: false,
      completed_sessions: 11,
      today_completed: true,
      score_history: [],
    },
    {
      id: 'stu-002',
      name: '이수아',
      level: 1,
      teacher_override_level: null,
      weak_areas: ['vocabulary', 'reasoning'],
      streak_count: 1,
      recent_avg: 4.5,
      needs_attention: true,
      completed_sessions: 5,
      today_completed: false,
      score_history: [],
    },
  ],
}
