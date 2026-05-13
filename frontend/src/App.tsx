import { AdminGftPage } from './pages/AdminGftPage';
import { GftPage } from './pages/GftPage';

export default function App() {
  if (window.location.pathname === '/admin/gft') {
    return <AdminGftPage />;
  }

  return <GftPage />;
}
