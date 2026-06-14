import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AuthGuard } from './AuthGuard';
import { AdminGuard } from './AdminGuard';
import { RouteError } from './RouteError';
import LoginPage from '@/features/auth/LoginPage';
import ResetRequestPage from '@/features/auth/ResetRequestPage';
import ResetConfirmPage from '@/features/auth/ResetConfirmPage';
import TasksTabPage from '@/features/tasks/TasksTabPage';
import TaskCreatePage from '@/features/tasks/TaskCreatePage';
import TaskCardPage from '@/features/tasks/TaskCardPage';
import RegistryPage from '@/features/admin/RegistryPage';
import ProfilePage from '@/features/profile/ProfilePage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage />, errorElement: <RouteError /> },
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
      { path: 'profile', element: <ProfilePage /> },
      {
        path: 'admin',
        element: <AdminGuard />,
        children: [{ index: true, element: <RegistryPage /> }],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);
