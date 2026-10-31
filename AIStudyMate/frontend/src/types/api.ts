export type UUID = string;
export type UserRole = "student" | "admin";
export type Difficulty = "easy" | "medium" | "hard";

export interface User {
  id: UUID; username: string; email: string; full_name: string;
  role: UserRole; is_active: boolean; created_at: string; updated_at: string;
}
export interface TokenPair { access_token: string; refresh_token: string; token_type: string }

export interface DocumentItem {
  id: UUID; title: string; original_filename: string; file_size: number; mime_type: string;
  processing_status: "uploaded" | "processing" | "ready" | "failed";
  indexing_status: "not_indexed" | "indexing" | "indexed" | "failed";
  page_count: number | null; requires_ocr: boolean; processing_error: string | null;
  index_error: string | null; indexed_at: string | null; created_at: string; updated_at: string;
}
export interface DocumentList { items: DocumentItem[]; total: number; page: number; per_page: number; pages: number }
export interface DocumentContent { document_id: UUID; title: string; pages: { page_number: number; text: string }[] }

export interface Citation { document_id: UUID; document_title: string; page_number: number; chunk_id: string }
export interface ChatSession { id: UUID; title: string; created_at: string; updated_at: string }
export interface ChatMessage { id: UUID; role: "user" | "assistant"; content: string; citations: Citation[] | null; created_at: string }
export interface ChatHistory { session_id: UUID; items: ChatMessage[] }
export interface SendMessageResponse { session_id: UUID; user_message: ChatMessage; assistant_message: ChatMessage; model: string | null }
export interface AgentResponse { session_id: UUID; answer: string; tools_used: string[]; citations: Citation[]; execution_steps: number; execution_status: "completed" | "failed" | "limit_reached"; model: string | null }

export interface QuizOption { id: UUID; text: string; order: number }
export interface QuizQuestion { id: UUID; question_text: string; order: number; options: QuizOption[]; source_references: Citation[] }
export interface QuizSummary { id: UUID; document_id: UUID; title: string; description: string | null; difficulty: Difficulty; question_count: number; created_at: string }
export interface QuizDetail extends QuizSummary { questions: QuizQuestion[] }
export interface QuizAttempt { id: UUID; quiz_id: UUID; started_at: string; completed_at: string | null; total_questions: number; quiz: QuizDetail }
export interface QuestionResult { question_id: UUID; question_text: string; selected_option_id: UUID; correct_option_id: UUID; is_correct: boolean; explanation: string; source_references: Citation[] }
export interface QuizResult { attempt_id: UUID; quiz_id: UUID; score: number; total_questions: number; percentage: number; completed_at: string; questions: QuestionResult[] }

export interface LatestResult { attempt_id: UUID; quiz_id: UUID; quiz_title: string; difficulty: Difficulty; score: number; total_questions: number; percentage: number; completed_at: string }
export interface QuizAccuracy { quiz_id: UUID; quiz_title: string; attempts: number; correct_answers: number; total_answers: number; accuracy_percentage: number }
export interface AnalyticsOverview { total_quizzes_attempted: number; average_score_percentage: number | null; highest_score_percentage: number | null; total_correct_answers: number; total_answered_questions: number; latest_results: LatestResult[]; accuracy_by_quiz: QuizAccuracy[] }
export interface ProgressPoint { date: string; attempts: number; average_score_percentage: number; correct_answers: number; total_questions: number }
export interface ProgressResponse { granularity: "day"; points: ProgressPoint[] }
export interface WeakTopic { quiz_id: UUID; topic: string; attempts: number; incorrect_answers: number; total_answers: number; accuracy_percentage: number }
export interface WeakTopicsResponse { topic_basis: "quiz_title"; items: WeakTopic[] }

export type FlashcardRating = "again" | "hard" | "good" | "easy";
export interface FlashcardSource { document_id: UUID; document_title: string; page_number: number | null; chunk_id: string | null }
export interface Flashcard { id: UUID; deck_id: UUID; front_text: string; back_text: string; explanation: string | null; card_order: number; source: FlashcardSource | null; created_at: string; updated_at: string }
export interface FlashcardDeckSummary { id: UUID; title: string; description: string | null; card_count: number; due_count: number; document_ids: UUID[]; created_at: string; updated_at: string }
export interface FlashcardDeck extends FlashcardDeckSummary { cards: Flashcard[] }
export interface DueFlashcards { items: Flashcard[]; total: number }
export interface FlashcardReview { id: UUID; flashcard_id: UUID; rating: FlashcardRating; reviewed_at: string; next_review_at: string; repetition_count: number; ease_factor: number; interval_days: number }
export interface FlashcardStats { total_decks: number; total_cards: number; due_cards: number; reviewed_cards: number; total_reviews: number; rating_counts: { rating: FlashcardRating; count: number }[] }
