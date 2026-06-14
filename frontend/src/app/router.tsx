import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AuthGuard } from './AuthGuard';
import { AdminGuard } from './AdminGuard';
import { RouteError } from './RouteError';
import LoginPage from '@/features/auth/LoginPage';
import RegisterPage from '@/features/auth/RegisterPage';
import ResetRequestPage from '@/features/auth/ResetRequestPage';
import ResetConfirmPage from '@/features/auth/ResetConfirmPage';
import TasksTabPage from '@/features/tasks/TasksTabPage';
import TaskCreatePage from '@/features/tasks/TaskCreatePage';
import TaskCardPage from '@/features/tasks/TaskCardPage';
import SearchPage from '@/features/search/SearchPage';
import RegistryPage from '@/features/admin/RegistryPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage />, errorElement: <RouteError /> },
  { path: '/register', element: <RegisterPage />, errorElement: <RouteError /> },
  { path: '/reset', element: <ResetRequestPage />, errorElement: <RouteError /> },
  { path: '/reset/confirm', element: <ResetConfirmPage />, errorElement: <RouteError /> },
  {
    path: '/',
    element: <AuthGuard />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Navigate to="/author" replace /> },
      { path: 'author', element: <TasksTabPage role="author" /> },
      { path: 'assignee', element: <TasksTabPage role="assignee" /> },
      { path: 'observer', element: <TasksTabPage role="observer" /> },
      { path: 'tasks/new', element: <TaskCreatePage /> },
      { path: 'tasks/:id', element: <TaskCardPage /> },
      { path: 'search', element: <SearchPage /> },
      {
        path: 'admin',
        element: <AdminGuard />,
        children: [{ index: true, element: <RegistryPage /> }],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);
