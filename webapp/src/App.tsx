import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { HomePage } from './pages/HomePage';
import { PlansPage } from './pages/PlansPage';
import { MyVpnPage } from './pages/MyVpnPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/plans" element={<PlansPage />} />
          <Route path="/my-vpn" element={<MyVpnPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
