import { useRouteError, isRouteErrorResponse, Link } from 'react-router-dom';

/** Экран ошибки маршрута (loader/render) в фирменном стиле вместо дефолтной страницы роутера. */
export function RouteError() {
  const error = useRouteError();

  let message = 'Произошла непредвиденная ошибка.';
  if (isRouteErrorResponse(error)) {
    message = `${error.status}. ${error.statusText || 'Страница недоступна.'}`;
  }

  return (
    <div className="auth-wrap">
      <div className="panel auth-card">
        <h1>Что-то пошло не так</h1>
        <p className="muted">{message}</p>
        <Link className="btn primary" to="/">
          На главную
        </Link>
      </div>
    </div>
  );
}
