import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';

const HomePage = lazy(() => import('./pages/HomePage').then(m => ({ default: m.HomePage })));
const PlansPage = lazy(() => import('./pages/PlansPage').then(m => ({ default: m.PlansPage })));
const MyVpnPage = lazy(() => import('./pages/MyVpnPage').then(m => ({ default: m.MyVpnPage })));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-40">
      <div className="w-6 h-6 rounded-full border-2 border-[#10B981] border-t-transparent animate-spin" />
    </div>
  );
}

export default function App({ onReady }: { onReady?: () => void }) {
  useEffect(() => {
    // Hide splash after a short delay to allow first render
    const timer = setTimeout(() => onReady?.(), 600);
    return () => clearTimeout(timer);
  }, [onReady]);

  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/plans" element={<PlansPage />} />
            <Route path="/my-vpn" element={<MyVpnPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
