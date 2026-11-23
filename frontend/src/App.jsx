import './App.css'

function App() {
  return (
    <div className="app-container">
      <header className="app-header">
        <h1>DealerOS</h1>
        <p className="app-subtitle">Automotive Inventory Reconciliation Platform</p>
      </header>
      <main className="app-content">
        <div className="status-card">
          <span className="status-badge">System Initialized</span>
          <h2>Frontend Environment Ready</h2>
          <p>
            React + Vite frontend is running and ready for reconciliation workflow integration.
          </p>
        </div>
      </main>
    </div>
  )
}

export default App
