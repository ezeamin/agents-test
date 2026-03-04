import { Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { LoginPage } from '@/routes/LoginPage';
import { DebugPage } from '@/routes/DebugPage';

export default function App() {
  return (
    <Routes>
      <Route path='/login' element={<LoginPage />} />

      {/* Protected routes */}
      <Route element={<ProtectedRoute />}>
        <Route index element={<DebugPage />} />
      </Route>

      {/* Fallback */}
      <Route path='*' element={<Navigate to='/' replace />} />
    </Routes>
  );
}
