import { Routes, Route } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import OverviewPage from '@/pages/OverviewPage'
import ForecastExplorerPage from '@/pages/ForecastExplorerPage'
import AccuracyPage from '@/pages/AccuracyPage'
import DataExplorerPage from '@/pages/DataExplorerPage'
import SettingsPage from '@/pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/"          element={<OverviewPage />} />
        <Route path="/forecast"  element={<ForecastExplorerPage />} />
        <Route path="/accuracy"  element={<AccuracyPage />} />
        <Route path="/data"      element={<DataExplorerPage />} />
        <Route path="/settings"  element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
