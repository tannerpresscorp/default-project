import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import * as Sentry from '@sentry/react';
import { App } from './App';
import { initSentry } from './sentry';
import './style.css';

initSentry();

const root = document.getElementById('root');

if (root) {
  createRoot(root).render(
    <StrictMode>
      <Sentry.ErrorBoundary fallback={<p>Something went wrong.</p>}>
        <App />
      </Sentry.ErrorBoundary>
    </StrictMode>,
  );
}
