import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

/** Верхнеуровневый перехватчик ошибок рендера, чтобы приложение не падало «в белый экран». */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Логируем для диагностики; в проде здесь может быть отправка в систему мониторинга.
    console.error('Необработанная ошибка интерфейса:', error, info);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="auth-wrap">
          <div className="panel auth-card">
            <h1>Что-то пошло не так</h1>
            <p className="muted">
              Перезагрузите страницу. Если ошибка повторяется, обратитесь к администратору.
            </p>
            <button className="btn primary" onClick={this.handleReload}>
              Перезагрузить
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
