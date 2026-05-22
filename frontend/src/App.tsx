import { AdminGftPage } from './pages/AdminGftPage';
import { GftPage } from './pages/GftPage';
import { AdminGftClinicalPage } from './pages/AdminGftClinicalPage';

export default function App() {
  if (window.location.pathname === '/admin/gft') {
    return <AdminGftPage />;
  }
  if (window.location.pathname === '/admin/gft/clinico') {
    return <AdminGftClinicalPage />;
  }

  return <GftPage />;
}
