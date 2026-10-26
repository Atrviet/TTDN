import { Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppShell } from "./components/AppShell";
import { AgentPage, ChatPage } from "./pages/ChatPages";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentDetailPage, DocumentsPage, UploadPage } from "./pages/DocumentPages";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProfilePage } from "./pages/ProfilePage";
import { QuizzesPage, QuizResultsPage, QuizTakePage } from "./pages/QuizPages";

export default function App() {
  return <Routes><Route path="/login" element={<LoginPage />} /><Route path="/register" element={<RegisterPage />} /><Route element={<ProtectedRoute />}><Route element={<AppShell />}><Route index element={<DashboardPage />} /><Route path="documents" element={<DocumentsPage />} /><Route path="documents/upload" element={<UploadPage />} /><Route path="documents/:id" element={<DocumentDetailPage />} /><Route path="chat" element={<ChatPage />} /><Route path="agent" element={<AgentPage />} /><Route path="quizzes" element={<QuizzesPage />} /><Route path="quizzes/:id/take" element={<QuizTakePage />} /><Route path="quiz-results/:attemptId" element={<QuizResultsPage />} /><Route path="analytics" element={<AnalyticsPage />} /><Route path="profile" element={<ProfilePage />} /><Route path="*" element={<NotFoundPage />} /></Route></Route></Routes>;
}
