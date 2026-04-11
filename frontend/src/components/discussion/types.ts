export type Speaker = 'moderator' | 'peer_a' | 'peer_b' | 'user'

export interface DisplayMessage {
  id: number
  speaker: Speaker
  content: string
  round: number
  isTyping?: boolean   // true = 타이핑 인디케이터 표시 중 (dots)
}

export const SPEAKERS: Record<Speaker, { name: string; emoji: string; color: string; bg: string; textColor: string }> = {
  moderator: { name: '모더레이터', emoji: 'M', color: '#7C3AED', bg: '#EDE9FE', textColor: '#5B21B6' },
  peer_a:    { name: '민지',       emoji: 'A', color: '#00C471', bg: '#E8F9F1', textColor: '#065F46' },
  peer_b:    { name: '준서',       emoji: 'B', color: '#FF9500', bg: '#FFF4E5', textColor: '#7A4A00' },
  user:      { name: '나',         emoji: '나', color: '#3182F6', bg: '#EEF3FF', textColor: '#1B64DA' },
}
