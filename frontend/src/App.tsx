
import { Provider } from 'react-redux';
import { store } from './store';
import Dashboard from './Dashboard';
import ErrorBoundary from './ErrorBoundary';

function App() {
  return (
    <Provider store={store}>
      <ErrorBoundary>
        <Dashboard />
      </ErrorBoundary>
    </Provider>
  );
}

export default App;
