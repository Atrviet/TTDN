import { Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppShell } from "./components/AppShell";
import { AgentPage, ChatPage } from "./pages/ChatPages";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentDetailPage, DocumentsPage, UploadPage } from "./pages/DocumentPages";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProfilePage } from "./pages/ProfilePage";
import { QuizzesPage, QuizResultsPage, QuizTakePage } from "./pages/QuizPages";
import { FlashcardDeckPage, FlashcardsPage, FlashcardStudyPage } from "./pages/FlashcardPages";
import { StudyPlanDetailPage, StudyPlansPage } from "./pages/StudyPlanPages";
import { TutorPage } from "./pages/TutorPage";
import { KnowledgeGraphPage } from "./pages/KnowledgeGraphPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { LearningWeaknessPage } from "./pages/LearningWeaknessPage";

export default function App() {
  return <Routes><Route path="/login" element={<LoginPage />} /><Route path="/register" element={<RegisterPage />} /><Route element={<ProtectedRoute />}><Route element={<AppShell />}><Route index element={<DashboardPage />} /><Route path="documents" element={<DocumentsPage />} /><Route path="documents/upload" element={<UploadPage />} /><Route path="documents/:id" element={<DocumentDetailPage />} /><Route path="chat" element={<ChatPage />} /><Route path="agent" element={<AgentPage />} /><Route path="quizzes" element={<QuizzesPage />} /><Route path="quizzes/:id/take" element={<QuizTakePage />} /><Route path="quiz-results/:attemptId" element={<QuizResultsPage />} /><Route path="flashcards" element={<FlashcardsPage />} /><Route path="flashcards/study" element={<FlashcardStudyPage />} /><Route path="flashcards/decks/:id" element={<FlashcardDeckPage />} /><Route path="study-plans" element={<StudyPlansPage />} /><Route path="study-plans/:id" element={<StudyPlanDetailPage />} /><Route path="tutor" element={<TutorPage />} /><Route path="knowledge-graphs" element={<KnowledgeGraphPage />} /><Route path="learning" element={<LearningWeaknessPage />} /><Route path="analytics" element={<AnalyticsPage />} /><Route path="profile" element={<ProfilePage />} /><Route path="*" element={<NotFoundPage />} /></Route></Route></Routes>;
}
